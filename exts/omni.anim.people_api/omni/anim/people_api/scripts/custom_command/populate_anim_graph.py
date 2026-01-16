import carb
import omni.kit.commands
from omni.anim.people_api.scripts.custom_command.command_manager import CustomCommandManager
from omni.anim.people_api.scripts.custom_command.defines import (
    CustomCommandTemplate,
    CustomCommand,
)
from pxr import Sdf, Usd

# Assume go to animations are all loaded at these paths
LIST_OF_GOTO_ANIMATIONS = [
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_1_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_1_mirror_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_2_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_2_mirror_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_3_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_3_mirror_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_4_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_4_mirror_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_5_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_5_mirror_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_7_skelanim",
    "/World/Characters/Biped_Setup/CharacterAnimation/Animation/stand_walk_7_mirror_skelanim",
]

# ========== Get functions ============


def get_anim_graph_prim(root_prim):
    if not (root_prim and root_prim.IsValid()):
        return None
    for prim in Usd.PrimRange(root_prim):
        if prim.GetTypeName() == "AnimationGraph":
            return prim
    return None


def get_state_machine_prim(root_prim):
    if not (root_prim and root_prim.IsValid()):
        return None
    for prim in Usd.PrimRange(root_prim):
        if prim.GetTypeName() == "StateMachine":
            return prim
    return None


def get_idle_state_prim(stage, state_machine_prim):
    if not (state_machine_prim and state_machine_prim.IsValid()):
        return None
    idle_state_prim = stage.GetPrimAtPath(f"{state_machine_prim.GetPrimPath()}/Idle")
    return idle_state_prim


def get_or_create_custom_animation_scope(stage, prim):
    scope_path = str(prim.GetPrimPath()) + "/CustomCommandAnimations"
    scope = stage.GetPrimAtPath(scope_path)
    # Create scope prim if not exist
    if not scope.IsValid():
        omni.kit.commands.execute(
            "CreatePrimWithDefaultXform", stage=stage, prim_type="Scope", prim_path=scope_path, select_new_prim=False
        )
        scope = stage.GetPrimAtPath(scope_path)
    return scope


def get_or_create_custom_animation(stage, biped_prim, custom_command: CustomCommand):
    scope_prim = get_or_create_custom_animation_scope(stage, biped_prim)
    anim_name = custom_command.name
    anim_prim_path = f"{scope_prim.GetPrimPath()}/{anim_name}"
    anim_prim = stage.GetPrimAtPath(anim_prim_path)
    if not anim_prim.IsValid():
        omni.kit.commands.execute(
            "CreatePayload",
            path_to=anim_prim_path,
            asset_path=custom_command.anim_path,
            usd_context=omni.usd.get_context(),
            select_prim=False,
        )
    anim_prim = stage.GetPrimAtPath(anim_prim_path)
    return anim_prim


# ========== Populate util functions ============


def populate_state(stage, prim_path):
    omni.kit.commands.execute("CreatePrimCommand", prim_type="State", prim_path=prim_path, select_new_prim=False)
    anim_state_prim = stage.GetPrimAtPath(prim_path)
    return anim_state_prim


def populate_transition(stage, from_state, to_state, prim_path, duration):
    omni.kit.commands.execute("CreatePrimCommand", prim_type="Transition", prim_path=prim_path, select_new_prim=False)
    anim_trans_to_prim = stage.GetPrimAtPath(prim_path)
    anim_trans_to_prim.GetAttribute("inputs:durationTime").Set(duration)
    omni.kit.commands.execute(
        "SetRelationshipTargets",
        relationship=anim_trans_to_prim.GetRelationship("inputs:state"),
        targets=[from_state.GetPrimPath()],
    )
    omni.kit.commands.execute(
        "SetRelationshipTargets",
        relationship=anim_trans_to_prim.GetRelationship("outputs:state"),
        targets=[to_state.GetPrimPath()],
    )
    return anim_trans_to_prim


def populate_action_condition(stage, trans_prim, action_value):
    condition_prim_path = f"{trans_prim.GetPrimPath()}/ConditionCompareVariable"
    omni.kit.commands.execute(
        "CreatePrimCommand", prim_type="ConditionCompareVariable", prim_path=condition_prim_path, select_new_prim=False
    )
    condition_prim = stage.GetPrimAtPath(condition_prim_path)
    condition_prim.GetAttribute("inputs:variableName").Set("Action")
    attr = condition_prim.CreateAttribute("inputs:value", Sdf.ValueTypeNames.String)
    attr.Set(action_value)
    omni.kit.commands.execute(
        "SetRelationshipTargets",
        relationship=trans_prim.GetRelationship("inputs:condition"),
        targets=[condition_prim.GetPrimPath()],
    )
    return condition_prim


def populate_animation_clip(stage, prim_path, anim_prim, custom_command: CustomCommand):
    omni.kit.commands.execute(
        "CreatePrimCommand", prim_type="AnimationClip", prim_path=prim_path, select_new_prim=False
    )
    anim_clip_prim = stage.GetPrimAtPath(prim_path)
    omni.kit.commands.execute(
        "SetRelationshipTargets",
        relationship=anim_clip_prim.GetRelationship("inputs:animationSource"),
        targets=[anim_prim.GetPrimPath()],
    )
    anim_clip_prim.GetAttribute("inputs:startTime").Set(custom_command.start_time)
    anim_clip_prim.GetAttribute("inputs:endTime").Set(custom_command.end_time)
    anim_clip_prim.GetAttribute("inputs:loop").Set(custom_command.loop)
    anim_clip_prim.GetAttribute("inputs:backwards").Set(custom_command.backwards)
    return anim_clip_prim


# ========== Populate functions ============


def populate_anim_graph():
    stage = omni.usd.get_context().get_stage()
    biped_prim = stage.GetPrimAtPath("/World/Characters/Biped_Setup")
    commands = CustomCommandManager.get_instance().get_all_custom_commands()
    for cmd in commands:
        if cmd.template == CustomCommandTemplate.TIMING or cmd.template == CustomCommandTemplate.TIMING_TO_OBJECT:
            populate_timing_template(stage, biped_prim, cmd)
        elif cmd.template == CustomCommandTemplate.GOTO_BLEND:
            populate_goto_blend_template(stage, biped_prim, cmd)


def populate_timing_template(
    stage, biped_prim, custom_command: CustomCommand, trans_to_duration=0.5, trans_back_duration=0.5
):
    # Check if anim garph is valid
    anim_graph_prim = get_anim_graph_prim(biped_prim)
    if not anim_graph_prim.IsValid():
        carb.log_error(
            f"No animation graph under prim {biped_prim.GetPrimPath()}, populating for {custom_command.name} fails."
        )
        return False
    state_machine_prim = get_state_machine_prim(anim_graph_prim)
    if not state_machine_prim.IsValid():
        carb.log_error(
            f"No state machine under prim {biped_prim.GetPrimPath()}, populating for {custom_command.name} fails."
        )
        return False
    idle_state_prim = get_idle_state_prim(stage, state_machine_prim)
    if not idle_state_prim.IsValid():
        carb.log_error(
            f"No idle state under prim {biped_prim.GetPrimPath()}, populating for {custom_command.name} fails."
        )
        return False
    # Do not re-populate existing state
    anim_state_prim_path = f"{state_machine_prim.GetPrimPath()}/state_{custom_command.name}"
    anim_state_prim = stage.GetPrimAtPath(anim_state_prim_path)
    if anim_state_prim.IsValid():
        carb.log_info(f"Biped has popualted for {custom_command.name} before. Skipping.")
        return True
    # Make sure new animation is loaded
    anim_prim = get_or_create_custom_animation(stage, biped_prim, custom_command)
    # Populate new anim graph nodes
    #   1. New state node
    anim_state_prim = populate_state(stage, anim_state_prim_path)
    #   2. Transition to the new state
    anim_trans_to_prim = populate_transition(
        stage,
        idle_state_prim,
        anim_state_prim,
        f"{state_machine_prim.GetPrimPath()}/trans_to_{custom_command.name}",
        trans_to_duration,
    )
    #   2.1 Transition to condition
    anim_trans_to_condition_prim = populate_action_condition(  # noqa: F841
        stage, anim_trans_to_prim, custom_command.name
    )
    #   3. Transition back to idle
    anim_trans_back_prim = populate_transition(
        stage,
        anim_state_prim,
        idle_state_prim,
        f"{state_machine_prim.GetPrimPath()}/trans_back_{custom_command.name}",
        trans_back_duration,
    )
    #   3.1 Transition back condition
    anim_trans_back_condition_prim = populate_action_condition(stage, anim_trans_back_prim, "None")  # noqa: F841
    #   4. Animation clip inside the state
    anim_clip_prim = populate_animation_clip(
        stage, f"{anim_state_prim.GetPrimPath()}/clip_{custom_command.name}", anim_prim, custom_command
    )
    omni.kit.commands.execute(
        "AddRelationshipTargetCommand",
        relationship=anim_state_prim.GetRelationship("inputs:pose"),
        target=anim_clip_prim.GetPrimPath(),
    )
    return True


def populate_goto_blend_template(
    stage, biped_prim, custom_command: CustomCommand, trans_to_duration=0.5, trans_back_duration=0.5
):
    biped_prim_path = biped_prim.GetPrimPath()  # noqa: F841
    # Check if anim garph is valid
    anim_graph_prim = get_anim_graph_prim(biped_prim)
    if not anim_graph_prim.IsValid():
        carb.log_error(
            f"No animation graph under prim {biped_prim.GetPrimPath()}, populating for {custom_command.name} fails."
        )
        return False
    state_machine_prim = get_state_machine_prim(anim_graph_prim)
    if not state_machine_prim.IsValid():
        carb.log_error(
            f"No state machine under prim {biped_prim.GetPrimPath()}, populating for {custom_command.name} fails."
        )
        return False
    idle_state_prim = get_idle_state_prim(stage, state_machine_prim)
    if not idle_state_prim.IsValid():
        carb.log_error(
            f"No idle state under prim {biped_prim.GetPrimPath()}, populating for {custom_command.name} fails."
        )
        return False
    # Do not re-populate existing state
    anim_state_prim_path = f"{state_machine_prim.GetPrimPath()}/state_{custom_command.name}"
    anim_state_prim = stage.GetPrimAtPath(anim_state_prim_path)
    if anim_state_prim.IsValid():
        carb.log_info(f"Biped has popualted for {custom_command.name} before. Skipping.")
        return True
    # Check if all go to animations exist
    for path in LIST_OF_GOTO_ANIMATIONS:
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid():
            carb.log_error(f"'{path}' is missing, populating for {custom_command.name} fails.")
            return False
    # Make sure new animation is loaded
    anim_prim = get_or_create_custom_animation(stage, biped_prim, custom_command)
    # Populate new anim graph nodes
    #   1. New state node
    anim_state_prim = populate_state(stage, anim_state_prim_path)
    #   2. Transition to the new state
    anim_trans_to_prim = populate_transition(
        stage,
        idle_state_prim,
        anim_state_prim,
        f"{state_machine_prim.GetPrimPath()}/trans_to_{custom_command.name}",
        trans_to_duration,
    )
    #   2.1 Transition to condition
    anim_trans_to_condition_prim = populate_action_condition(  # noqa: F841
        stage, anim_trans_to_prim, custom_command.name
    )
    #   3. Transition back to idle
    anim_trans_back_prim = populate_transition(
        stage,
        anim_state_prim,
        idle_state_prim,
        f"{state_machine_prim.GetPrimPath()}/trans_back_{custom_command.name}",
        trans_back_duration,
    )
    #   3.1 Transition back condition
    anim_trans_back_condition_prim = populate_action_condition(stage, anim_trans_back_prim, "None")  # noqa: F841
    #   4. Nodes inside state
    #   4.1 Animation clip node
    anim_clip_prim_path = f"{anim_state_prim.GetPrimPath()}/clip_{custom_command.name}"
    anim_clip_prim = populate_animation_clip(stage, anim_clip_prim_path, anim_prim, custom_command)  # noqa: F841
    #   4.2 Filter node
    filter_prim_path = f"{anim_state_prim.GetPrimPath()}/filter"
    omni.kit.commands.execute(
        "CreatePrimCommand", prim_type="Filter", prim_path=filter_prim_path, select_new_prim=False
    )
    filter_prim = stage.GetPrimAtPath(filter_prim_path)
    filter_prim.GetAttribute("inputs:joints").Set(["Chest"])  # TBD
    omni.kit.commands.execute(
        "AddRelationshipTargetCommand",
        relationship=filter_prim.GetRelationship("inputs:pose"),
        target=anim_clip_prim_path,
    )
    #   4.3 Motion Matching node
    motion_matching_prim_path = f"{anim_state_prim.GetPrimPath()}/MotionMatching"
    omni.kit.commands.execute(
        "CreatePrimCommand", prim_type="MotionMatching", prim_path=motion_matching_prim_path, select_new_prim=False
    )
    motion_matching_prim = stage.GetPrimAtPath(motion_matching_prim_path)
    for path in LIST_OF_GOTO_ANIMATIONS:
        omni.kit.commands.execute(
            "AddRelationshipTargetCommand",
            relationship=motion_matching_prim.GetRelationship("inputs:clips"),
            target=path,
        )
    motion_matching_prim.GetAttribute("inputs:joints").Set(["Pelvis", "L_Ball", "R_Ball"])  # TBD
    path_points_prim_path = f"{anim_state_prim.GetPrimPath()}/PathPoints"
    omni.kit.commands.execute(
        "CreatePrimCommand", prim_type="ReadVariable", prim_path=path_points_prim_path, select_new_prim=False
    )
    path_points_prim = stage.GetPrimAtPath(path_points_prim_path)
    path_points_prim.GetAttribute("inputs:variableName").Set("PathPoints")
    omni.kit.commands.execute(
        "AddRelationshipTargetCommand",
        relationship=motion_matching_prim.GetRelationship("inputs:pathPoints"),
        target=path_points_prim_path,
    )
    #   4.4 Blend node
    blend_prim_path = f"{anim_state_prim.GetPrimPath()}/Blend"
    omni.kit.commands.execute("CreatePrimCommand", prim_type="Blend", prim_path=blend_prim_path, select_new_prim=False)
    blend_prim = stage.GetPrimAtPath(blend_prim_path)
    blend_weight_prim_path = f"{anim_state_prim.GetPrimPath()}/BlendWeights"

    # in case Value0 does not exist
    # omni.kit.commands.execute(
    #     "CreateUsdAttribute",
    #     prim=anim_graph_prim,
    #     attr_name="anim:graph:variable:NewVariable",
    #     attr_type=Sdf.ValueTypeNames.Float,
    #     attr_value=0.0,
    # )
    # omni.kit.commands.execute(
    #     "RenameAnimationGraphVariableAttributeCommand",
    #     prim=anim_graph_prim,
    #     old_attr_name="anim:graph:variable:NewVariable",
    #     new_attr_name="anim:graph:variable:Value0",
    # )
    omni.kit.commands.execute(
        "CreatePrimCommand", prim_type="ReadVariable", prim_path=blend_weight_prim_path, select_new_prim=False
    )
    blend_weight_prim = stage.GetPrimAtPath(blend_weight_prim_path)
    blend_weight_prim.GetAttribute("inputs:variableName").Set("Value0")
    omni.kit.commands.execute(
        "AddRelationshipTargetCommand",
        relationship=blend_prim.GetRelationship("inputs:blendWeight"),
        target=blend_weight_prim_path,
    )
    omni.kit.commands.execute(
        "AddRelationshipTargetCommand",
        relationship=blend_prim.GetRelationship("inputs:pose0"),
        target=filter_prim_path,
    )
    omni.kit.commands.execute(
        "AddRelationshipTargetCommand",
        relationship=blend_prim.GetRelationship("inputs:pose1"),
        target=motion_matching_prim_path,
    )
    omni.kit.commands.execute(
        "AddRelationshipTargetCommand",
        relationship=anim_state_prim.GetRelationship("inputs:pose"),
        target=blend_prim_path,
    )
    return True
