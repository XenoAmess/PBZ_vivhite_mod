#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "baiqi_appearance_schema.generated.h"

// The declared fields are the subset used by the versioned appearance rows.
UENUM()
enum class EAppearanceType : uint8
{
    Body, Hat, Beard, Hairstyle, Outfit, Neck, MeshBand, BrowLashCard
};

USTRUCT()
struct FFlowLocText
{
    GENERATED_BODY()
    UPROPERTY() FString Namespace;
    UPROPERTY() FString Key;
    UPROPERTY() FText ValueCache;
};

USTRUCT()
struct FItemDataBase : public FTableRowBase
{
    GENERATED_BODY()
    UPROPERTY() FName ItemId;
};

USTRUCT()
struct FPBZAppearanceStruct : public FItemDataBase
{
    GENERATED_BODY()
    UPROPERTY() FFlowLocText AppearanceName;
    UPROPERTY() FFlowLocText AppearanceDesc;
    UPROPERTY() TSoftObjectPtr<UObject> AppearanceTexture;
    UPROPERTY() EAppearanceType AppearanceType = EAppearanceType::Body;
    UPROPERTY() TSoftObjectPtr<UObject> BodyMeshAsset;
    UPROPERTY() TSoftObjectPtr<UObject> HeadAsset;
    UPROPERTY() TSoftObjectPtr<UObject> MeshBandAsset;
    UPROPERTY() TSoftObjectPtr<UObject> BrowLashCardAsset;
    UPROPERTY() FName OutfitBodyItem;
    UPROPERTY() FName OutfitHairStyleItem;
    UPROPERTY() FName OutfitSequenceHairStyleItem;
    UPROPERTY() FName OutfitMeshBandItem;
    UPROPERTY() FName OutfitBrowLashCardItem;
    UPROPERTY() bool bDefaultHatHidden = false;
    UPROPERTY() bool bObtainableInGame = false;
};
