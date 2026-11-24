#include "AnimGraphNode_ComponentToLocalSpace.h"
#include "AnimGraphNode_CopyBone.h"
#include "AnimGraphNode_LinkedInputPose.h"
#include "AnimGraphNode_LocalToComponentSpace.h"
#include "AnimGraphNode_ModifyBone.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Engine/World.h"

FString UPBZModToolsLibrary::BuildBaiQiBridgeGraph(UAnimBlueprint* Blueprint, const FString& Spec)
{
	if (!Blueprint || !Blueprint->TargetSkeleton)
	{
		return TEXT("error: missing blueprint skeleton");
	}
	const TSharedPtr<FJsonObject> Plan = ParseJson(Spec);
	const TArray<TSharedPtr<FJsonValue>>* Steps = nullptr;
	if (!Plan || !Plan->TryGetArrayField(TEXT("steps"), Steps) || Steps->IsEmpty())
	{
		return TEXT("error: missing bridge steps");
	}
	const FReferenceSkeleton& Ref = Blueprint->TargetSkeleton->GetReferenceSkeleton();
	for (const TSharedPtr<FJsonValue>& Value : *Steps)
	{
		const TSharedPtr<FJsonObject> Step = Value->AsObject();
		const FName Source(*Step->GetStringField(TEXT("source")));
		const FName Target(*Step->GetStringField(TEXT("target")));
		if (Ref.FindBoneIndex(Source) == INDEX_NONE || Ref.FindBoneIndex(Target) == INDEX_NONE ||
			!Target.ToString().StartsWith(TEXT("BaiQi_")))
		{
			return FString::Printf(TEXT("error: unexpected bridge binding %s -> %s"), *Source.ToString(), *Target.ToString());
		}
	}
	UEdGraph* Graph = nullptr;
	for (UEdGraph* Candidate : Blueprint->FunctionGraphs)
	{
		if (Candidate && Candidate->GetFName() == UEdGraphSchema_K2::GN_AnimGraph)
		{
			Graph = Candidate;
			break;
		}
	}
	if (!Graph)
	{
		return TEXT("error: missing animation graph");
	}
	UAnimGraphNode_Root* Root = nullptr;
	for (UEdGraphNode* Node : TArray<UEdGraphNode*>(Graph->Nodes))
	{
		if (UAnimGraphNode_Root* Candidate = Cast<UAnimGraphNode_Root>(Node))
		{
			Root = Candidate;
		}
		else
		{
			Graph->RemoveNode(Node);
		}
	}
	if (!Root)
	{
		return TEXT("error: missing output pose");
	}
	const UEdGraphSchema* Schema = Graph->GetSchema();
	auto PosePin = [](UEdGraphNode* Node, EEdGraphPinDirection Direction)
	{
		for (UEdGraphPin* Pin : Node->Pins)
		{
			const UObject* Type = Pin->PinType.PinSubCategoryObject.Get();
			if (Pin->Direction == Direction && (Type == FPoseLink::StaticStruct() || Type == FComponentSpacePoseLink::StaticStruct()))
			{
				return Pin;
			}
		}
		return static_cast<UEdGraphPin*>(nullptr);
	};
	FGraphNodeCreator<UAnimGraphNode_LinkedInputPose> InputCreator(*Graph);
	UAnimGraphNode_LinkedInputPose* Input = InputCreator.CreateNode();
	Input->NodePosX = 0;
	InputCreator.Finalize();
	UEdGraphPin* Previous = PosePin(Input, EGPD_Output);
	auto Append = [&](UEdGraphNode* Node)
	{
		UEdGraphPin* Next = PosePin(Node, EGPD_Input);
		if (!Previous || !Next || !Schema->TryCreateConnection(Previous, Next))
		{
			return false;
		}
		Previous = PosePin(Node, EGPD_Output);
		return Previous != nullptr;
	};
	FGraphNodeCreator<UAnimGraphNode_LocalToComponentSpace> ComponentCreator(*Graph);
	UAnimGraphNode_LocalToComponentSpace* ToComponent = ComponentCreator.CreateNode();
	ToComponent->NodePosX = 240;
	ComponentCreator.Finalize();
	if (!Append(ToComponent))
	{
		return TEXT("error: input pose conversion did not connect");
	}
	int32 X = 500;
	for (const TSharedPtr<FJsonValue>& Value : *Steps)
	{
		const TSharedPtr<FJsonObject> Step = Value->AsObject();
		const FName Target(*Step->GetStringField(TEXT("target")));
		FGraphNodeCreator<UAnimGraphNode_CopyBone> CopyCreator(*Graph);
		UAnimGraphNode_CopyBone* Copy = CopyCreator.CreateNode();
		Copy->Node.SourceBone.BoneName = FName(*Step->GetStringField(TEXT("source")));
		Copy->Node.TargetBone.BoneName = Target;
		Copy->Node.bCopyRotation = true;
		Copy->Node.ControlSpace = BCS_ComponentSpace;
		Copy->Node.Alpha = static_cast<float>(Step->GetNumberField(TEXT("weight")));
		Copy->NodePosX = X;
		X += 240;
		CopyCreator.Finalize();
		if (!Append(Copy))
		{
			return TEXT("error: rotation copy did not connect");
		}
		const TArray<TSharedPtr<FJsonValue>>* Offset = nullptr;
		if (Step->TryGetArrayField(TEXT("offset_xyzw"), Offset))
		{
			if (Offset->Num() != 4) return TEXT("error: invalid rotation offset");
			const FQuat Rotation((*Offset)[0]->AsNumber(), (*Offset)[1]->AsNumber(),
				(*Offset)[2]->AsNumber(), (*Offset)[3]->AsNumber());
			FGraphNodeCreator<UAnimGraphNode_ModifyBone> OffsetCreator(*Graph);
			UAnimGraphNode_ModifyBone* Modify = OffsetCreator.CreateNode();
			Modify->Node.BoneToModify.BoneName = Target;
			Modify->Node.Rotation = Rotation.Rotator();
			Modify->Node.RotationMode = BMM_Additive;
			Modify->Node.RotationSpace = BCS_BoneSpace;
			Modify->NodePosX = X;
			X += 240;
			OffsetCreator.Finalize();
			if (!Append(Modify))
			{
				return TEXT("error: rotation offset did not connect");
			}
		}
	}
	FGraphNodeCreator<UAnimGraphNode_ComponentToLocalSpace> LocalCreator(*Graph);
	UAnimGraphNode_ComponentToLocalSpace* ToLocal = LocalCreator.CreateNode();
	ToLocal->NodePosX = X;
	LocalCreator.Finalize();
	Root->NodePosX = X + 240;
	if (!Append(ToLocal) || !Schema->TryCreateConnection(Previous, Root->FindPin(TEXT("Result"), EGPD_Input)))
	{
		return TEXT("error: output pose did not connect");
	}
	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
	FKismetEditorUtilities::CompileBlueprint(Blueprint);
	if (Blueprint->Status == BS_Error || !Blueprint->GeneratedClass)
	{
		return TEXT("error: animation graph compilation failed");
	}
	Blueprint->MarkPackageDirty();
	return FString::Printf(TEXT("ok rotation steps=%d"), Steps->Num());
}

FString UPBZModToolsLibrary::SampleBaiQiBridgePose(USkeletalMesh* Mesh, UAnimSequence* Animation, float Fraction)
{
	if (!Mesh || !Animation || !Mesh->GetPostProcessAnimBlueprint())
	{
		return TEXT("error: missing editor fixture inputs");
	}
	Animation->WaitOnExistingCompression(true);
	UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!World)
	{
		return TEXT("error: editor world unavailable");
	}
	USkeletalMeshComponent* Component = NewObject<USkeletalMeshComponent>(GetTransientPackage());
	Component->SetSkeletalMeshAsset(Mesh);
	Component->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	Component->RegisterComponentWithWorld(World);
	Component->SetAnimation(Animation);
	Component->SetPosition(FMath::Clamp(Fraction, 0.0f, 1.0f) * Animation->GetPlayLength(), false);
	Component->TickAnimation(0.0f, false);
	Component->RefreshBoneTransforms();
	if (!Component->GetPostProcessInstance())
	{
		Component->DestroyComponent();
		return TEXT("error: post-process instance did not initialize");
	}
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	const TArray<FTransform>& Transforms = Component->GetComponentSpaceTransforms();
	if (Transforms.Num() != Ref.GetNum())
	{
		Component->DestroyComponent();
		return TEXT("error: incomplete editor pose");
	}
	FString Json = TEXT("[");
	for (int32 Index = 0; Index < Transforms.Num(); ++Index)
	{
		Json += FString::Printf(TEXT("%s{\"name\":\"%s\",%s}"), Index ? TEXT(",") : TEXT(""),
			*Ref.GetBoneName(Index).ToString(), *TransformToJson(Transforms[Index]));
	}
	Component->DestroyComponent();
	return Json + TEXT("]");
}
