#include "Engine/DataTable.h"
#include "Kismet2/StructureEditorUtils.h"
#include "Misc/PackageName.h"
#include "UObject/StructOnScope.h"
#include "StructUtils/UserDefinedStruct.h"
#include "UserDefinedStructure/UserDefinedStructEditorData.h"

namespace
{
constexpr TCHAR BaiQiOptionsSchema[] = TEXT("/PBZModLoader/Options/S_PBZOutfitOption");

UUserDefinedStruct* GetBaiQiOptionsSchema(const TSharedPtr<FJsonObject>& Spec)
{
    const FString ObjectPath = FString(BaiQiOptionsSchema) + TEXT(".S_PBZOutfitOption");
    if (UUserDefinedStruct* Existing = LoadObject<UUserDefinedStruct>(nullptr, *ObjectPath, nullptr, LOAD_NoWarn))
    {
        return Existing;
    }
    UPackage* Package = CreatePackage(BaiQiOptionsSchema);
    UUserDefinedStruct* Schema = FStructureEditorUtils::CreateUserDefinedStruct(
        Package, FName(TEXT("S_PBZOutfitOption")), RF_Public | RF_Standalone | RF_Transactional);
    if (!Schema || !FGuid::ParseExact(Spec->GetStringField(TEXT("schema_guid")), EGuidFormats::Digits, Schema->Guid))
    {
        return nullptr;
    }
    TArray<FStructVariableDescription>& Variables = FStructureEditorUtils::GetVarDesc(Schema);
    Variables.Reset();
    for (const TSharedPtr<FJsonValue>& Field : Spec->GetArrayField(TEXT("option_schema")))
    {
        const TSharedPtr<FJsonObject> Column = Field->AsObject();
        const FString Name = Column->GetStringField(TEXT("name"));
        const FString Kind = Column->GetStringField(TEXT("kind"));
        FStructVariableDescription& Var = Variables.AddDefaulted_GetRef();
        Var.VarName = FName(*Name);
        FString Guid;
        Name.Split(TEXT("_"), nullptr, &Guid, ESearchCase::CaseSensitive, ESearchDir::FromEnd);
        if (!FGuid::ParseExact(Guid, EGuidFormats::Digits, Var.VarGuid))
        {
            return nullptr;
        }
        FString Friendly;
        Name.Split(TEXT("_"), &Friendly, nullptr);
        Var.FriendlyName = Friendly;
        Var.ContainerType = Column->GetBoolField(TEXT("array")) ? EPinContainerType::Array : EPinContainerType::None;
        if (Kind == TEXT("TextProperty")) Var.Category = UEdGraphSchema_K2::PC_Text;
        else if (Kind == TEXT("NameProperty")) Var.Category = UEdGraphSchema_K2::PC_Name;
        else if (Kind == TEXT("IntProperty")) Var.Category = UEdGraphSchema_K2::PC_Int;
        else if (Kind == TEXT("BoolProperty")) Var.Category = UEdGraphSchema_K2::PC_Boolean;
        else if (Kind == TEXT("SoftObjectProperty"))
        {
            Var.Category = UEdGraphSchema_K2::PC_SoftObject;
            Var.SubCategoryObject = UObject::StaticClass();
        }
        else if (Kind == TEXT("DoubleProperty"))
        {
            Var.Category = UEdGraphSchema_K2::PC_Real;
            Var.SubCategory = UEdGraphSchema_K2::PC_Double;
        }
        else return nullptr;
    }
    Schema->Status = UDSS_Dirty;
    FStructureEditorUtils::CompileStructure(Schema);
    if (Schema->Status != UDSS_UpToDate)
    {
        return nullptr;
    }
    FAssetRegistryModule::AssetCreated(Schema);
    Schema->MarkPackageDirty();
    return Schema;
}

UDataTable* MakeBaiQiTable(const FString& Path, UScriptStruct* RowStruct)
{
    UPackage* Package = CreatePackage(*Path);
    const FName Name(*FPackageName::GetShortName(Path));
    UDataTable* Table = FindObject<UDataTable>(Package, *Name.ToString());
    if (!Table)
    {
        Table = NewObject<UDataTable>(Package, Name, RF_Public | RF_Standalone | RF_Transactional);
        FAssetRegistryModule::AssetCreated(Table);
    }
    else
    {
        Table->EmptyTable();
    }
    Table->RowStruct = RowStruct;
    Table->MarkPackageDirty();
    return Table;
}
}

FString UPBZModToolsLibrary::BuildBaiQiOutfitTables(const FString& SpecText)
{
    const TSharedPtr<FJsonObject> Spec = ParseJson(SpecText);
    if (!Spec) return TEXT("error: invalid outfit specification");
    UUserDefinedStruct* OptionsSchema = GetBaiQiOptionsSchema(Spec);
    UScriptStruct* AppearanceSchema = LoadObject<UScriptStruct>(
        nullptr, TEXT("/Script/ProjectPBZ.PBZAppearanceStruct"));
    if (!AppearanceSchema || !OptionsSchema) return TEXT("error: missing row schemas");

    UDataTable* Outfit = MakeBaiQiTable(Spec->GetStringField(TEXT("outfit_table")), AppearanceSchema);
    Outfit->bIgnoreMissingFields = true;
    FString Rows;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Rows);
    FJsonSerializer::Serialize(Spec->GetArrayField(TEXT("appearance_rows")), Writer);
    const TArray<FString> Errors = Outfit->CreateTableFromJSONString(Rows);
    if (!Errors.IsEmpty()) return FString::Join(Errors, TEXT("\n"));

    UDataTable* Options = MakeBaiQiTable(Spec->GetStringField(TEXT("options_table")), OptionsSchema);
    FStructOnScope Row(OptionsSchema);
    uint8* Data = Row.GetStructMemory();
    for (TFieldIterator<FProperty> Property(OptionsSchema); Property; ++Property)
    {
        const FString Name = Property->GetName();
        if (Name.StartsWith(TEXT("Label_")))
        {
            CastFieldChecked<FTextProperty>(*Property)->SetPropertyValue_InContainer(
                Data, FText::FromString(Spec->GetStringField(TEXT("option_label"))));
        }
        else if (Name.StartsWith(TEXT("Type_")))
        {
            CastFieldChecked<FNameProperty>(*Property)->SetPropertyValue_InContainer(Data, FName(TEXT("Hide")));
        }
        else if (Name.StartsWith(TEXT("OutfitMesh_")))
        {
            CastFieldChecked<FSoftObjectProperty>(*Property)->SetPropertyValue_InContainer(
                Data, FSoftObjectPtr(FSoftObjectPath(Spec->GetStringField(TEXT("mesh")))));
        }
        else if (Name.StartsWith(TEXT("HideSlots_")))
        {
            FArrayProperty* Array = CastFieldChecked<FArrayProperty>(*Property);
            FScriptArrayHelper Slots(Array, Array->ContainerPtrToValuePtr<void>(Data));
            for (const TSharedPtr<FJsonValue>& Slot : Spec->GetArrayField(TEXT("coat_slots")))
            {
                CastFieldChecked<FIntProperty>(Array->Inner)->SetPropertyValue(
                    Slots.GetRawPtr(Slots.AddValue()), static_cast<int32>(Slot->AsNumber()));
            }
        }
    }
    Options->AddRow(TEXT("BaiQi_RemoveCoat"), Data, OptionsSchema);
    return FString::Printf(TEXT("ok appearance=%d options=%d"), Outfit->GetRowMap().Num(), Options->GetRowMap().Num());
}
