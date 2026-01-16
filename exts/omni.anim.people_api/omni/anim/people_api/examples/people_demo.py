from isaacsim import SimulationApp

import os

simulation_app = SimulationApp({"headless": False})

import omni.kit.app

# Enable required extensions before importing their modules.
_EXTENSIONS = (
    "omni.anim.navigation.core",
    "omni.anim.graph.core",
    "omni.anim.people_api",
)
_ext_mgr = omni.kit.app.get_app().get_extension_manager()
for _ext in _EXTENSIONS:
    _ext_mgr.set_extension_enabled_immediate(_ext, True)

# Allow extensions to finish loading before importing their modules.
for _ in range(10):
    simulation_app.update()

import carb
import omni.kit.commands
import omni.timeline
import omni.usd
import omni.anim.navigation.core as nav
import NavSchema
from pxr import Gf, Sdf, Usd, UsdGeom

from isaacsim.core.api import World
from isaacsim.core.utils import prims
from isaacsim.core.utils.stage import is_stage_loading

from omni.anim.people_api.settings import PeopleSettings
from omni.anim.people_api.scripts.character_setup import CharacterSetup, CharacterBehavior
from omni.anim.people_api.scripts.custom_command.command_manager import CustomCommandManager
from omni.anim.people_api.scripts.utils import Utils


NUM_PEOPLE = 5
ROBOT_PRIM_PATH = "/World/Robot"
CHAR_ROOT = "/World/Characters"
NAVMESH_CENTER = (0.0, 0.0, 0.0)
NAVMESH_SCALE = (25.0, 25.0, 5.0)  # size of the navmesh volume
GOTO_GOAL = (2.0, 0.0, 0.0)
GOTO_YAW_DEG = 0.0
GOTO_IDLE_SECONDS = 2.0
RUN_STEPS = int(os.environ.get("PEOPLE_RUN_STEPS", "0"))


def wait_for_animation_graph(stage, max_updates=600):
    for _ in range(max_updates):
        for prim in stage.Traverse():
            if prim.GetTypeName() == "AnimationGraph":
                return prim
        simulation_app.update()
    return None


def find_skelroot(stage, character_root_path):
    root_prim = stage.GetPrimAtPath(character_root_path)
    if not root_prim or not root_prim.IsValid():
        return None
    for prim in Usd.PrimRange(root_prim):
        if prim.GetTypeName() == "SkelRoot":
            return prim
    return None


def clear_behavior_scripts(root_prim):
    cleared = []
    for prim in Usd.PrimRange(root_prim):
        attr = prim.GetAttribute("omni:scripting:scripts")
        if not attr or not attr.IsValid():
            continue
        scripts = attr.Get()
        if scripts:
            # Override any referenced scripts with an empty list.
            attr.Set([])
            cleared.append((str(prim.GetPrimPath()), scripts))
    return cleared


def apply_behavior_to_skelroot(skelroot_prim, anim_graph_prim, script_path):
    omni.kit.commands.execute(
        "ApplyAnimationGraphAPICommand",
        paths=[Sdf.Path(skelroot_prim.GetPrimPath())],
        animation_graph_path=Sdf.Path(anim_graph_prim.GetPrimPath()),
    )
    omni.kit.commands.execute("ApplyScriptingAPICommand", paths=[Sdf.Path(skelroot_prim.GetPrimPath())])
    attr = skelroot_prim.GetAttribute("omni:scripting:scripts")
    attr.Set([r"{}".format(script_path)])
    Utils.add_colliders(skelroot_prim)
    Utils.add_rigid_body_dynamics(skelroot_prim)


def ensure_navmesh_volume():
    stage = omni.usd.get_context().get_stage()

    def iter_volumes():
        for prim in stage.Traverse():
            if prim.GetTypeName() == "NavMeshVolume" or prim.IsA(NavSchema.NavMeshVolume):
                yield prim

    for prim in iter_volumes():
        return prim

    omni.kit.commands.execute(
        "CreateNavMeshVolumeCommand",
        parent_prim_path=Sdf.Path.emptyPath,
        volume_type=0,
        position=NAVMESH_CENTER,
    )
    for _ in range(120):
        simulation_app.update()
        for prim in iter_volumes():
            nav_volume = NavSchema.NavMeshVolume(prim)
            nav_type_attr = nav_volume.GetNavVolumeTypeAttr()
            if nav_type_attr:
                nav_type_attr.Set("Include")
            xform = UsdGeom.Xformable(prim)
            translate_op = next(
                (op for op in xform.GetOrderedXformOps() if op.GetOpType() == UsdGeom.XformOp.TypeTranslate),
                None,
            )
            if translate_op is None:
                translate_op = xform.AddTranslateOp()
            translate_op.Set(Gf.Vec3f(*NAVMESH_CENTER))

            scale_op = next(
                (op for op in xform.GetOrderedXformOps() if op.GetOpType() == UsdGeom.XformOp.TypeScale),
                None,
            )
            if scale_op is None:
                scale_op = xform.AddScaleOp()
            scale_op.Set(Gf.Vec3f(*NAVMESH_SCALE))
            return prim

    raise RuntimeError("Failed to create NavMeshVolume")


def bake_navmesh(max_updates=600):
    inav = nav.acquire_interface()
    inav.start_navmesh_baking()
    for _ in range(max_updates):
        simulation_app.update()
        navmesh = inav.get_navmesh()
        if navmesh is not None:
            return navmesh
    raise RuntimeError("Navmesh bake timed out")


def wait_for_people_api(max_updates=300):
    for _ in range(max_updates):
        if CustomCommandManager.get_instance() is not None:
            return True
        simulation_app.update()
    return False


def describe_anim_graph_binding(skelroot_prim):
    import AnimGraphSchema

    has_api = skelroot_prim.HasAPI(AnimGraphSchema.AnimationGraphAPI)
    rel = skelroot_prim.GetRelationship("animationGraph")
    targets = [str(target) for target in rel.GetTargets()] if rel else []
    return has_api, targets


def verify_character_binding(skelroot_prim):
    import omni.anim.graph.core as ag

    has_api, targets = describe_anim_graph_binding(skelroot_prim)
    character = ag.get_character(str(skelroot_prim.GetPrimPath()))
    status = "OK" if character else "MISSING"
    try:
        count = ag.get_character_count()
    except Exception as exc:
        count = f"error:{exc}"
    print(
        f"Character bind {skelroot_prim.GetPrimPath()}: api={has_api} graph={targets} ag={status} count={count}"
    )


def inject_goal_commands(character_names, goal_point, yaw_deg=0.0, idle_seconds=2.0):
    goal_x, goal_y, goal_z = goal_point
    for name in character_names:
        command_list = [
            f"{name} GoTo {goal_x} {goal_y} {goal_z} {yaw_deg}",
            f"{name} Idle {idle_seconds}",
        ]
        Utils.runtime_inject_command(name, command_list, force_inject=True)
    return None


def main():
    context = omni.usd.get_context()
    context.new_stage()
    for _ in range(2):
        simulation_app.update()

    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    settings = carb.settings.get_settings()
    settings.set(PeopleSettings.CHARACTER_PRIM_PATH, CHAR_ROOT)
    settings.set(PeopleSettings.BEHAVIOR_SCRIPT_PATH, CharacterBehavior.RANDOM_GOTO.value.script_path)
    settings.set(PeopleSettings.NAVMESH_ENABLED, True)
    settings.set(PeopleSettings.DYNAMIC_AVOIDANCE_ENABLED, True)

    if not wait_for_people_api():
        raise RuntimeError("People API not ready; CustomCommandManager not initialized.")

    if not prims.is_prim_path_valid(ROBOT_PRIM_PATH):
        prims.create_prim(ROBOT_PRIM_PATH, "Xform")

    ensure_navmesh_volume()
    bake_navmesh()

    timeline = omni.timeline.get_timeline_interface()
    timeline.set_auto_update(True)
    timeline.stop()

    cs = CharacterSetup(
        ROBOT_PRIM_PATH,
        num_characters=0,
        starting_point=(0.0, 0.0, 0.0),
        is_warmup=False,
    )
    stage = omni.usd.get_context().get_stage()
    anim_graph = wait_for_animation_graph(stage)
    if anim_graph is None:
        raise RuntimeError("AnimationGraph prim not found; cannot animate characters.")
    cs.anim_graph_prim = anim_graph

    names = cs.load_random_characters(NUM_PEOPLE, CharacterBehavior.RANDOM_GOTO)

    # Wait for character assets/payloads to load before applying anim graph/scripts again.
    for _ in range(120):
        if not is_stage_loading():
            break
        simulation_app.update()

    # Apply animation graph + behavior script directly to each SkelRoot.
    script_path = CharacterBehavior.RANDOM_GOTO.value.script_path
    skelroots = []
    for name in names:
        root_path = f"{CHAR_ROOT}/{name}"
        root_prim = stage.GetPrimAtPath(root_path)
        if not root_prim or not root_prim.IsValid():
            print(f"Root prim not found: {root_path}")
            continue
        cleared = clear_behavior_scripts(root_prim)
        if cleared:
            print(f"Cleared scripts under {root_path}: {cleared}")
        for _ in range(5):
            simulation_app.update()
        skelroot = None
        for _ in range(120):
            skelroot = find_skelroot(stage, root_path)
            if skelroot:
                break
            simulation_app.update()
        if skelroot is None:
            print(f"SkelRoot not found for {root_path}")
            continue
        print(f"Using SkelRoot {skelroot.GetPrimPath()} for {root_path}")
        apply_behavior_to_skelroot(skelroot, anim_graph, script_path)
        skelroots.append(skelroot)

    print("Spawned:", names)

    timeline.play()
    for _ in range(60):
        world.step(render=True)
    for skelroot in skelroots:
        verify_character_binding(skelroot)

    inject_goal_commands(names, GOTO_GOAL, yaw_deg=GOTO_YAW_DEG, idle_seconds=GOTO_IDLE_SECONDS)

    if RUN_STEPS > 0:
        for _ in range(RUN_STEPS):
            world.step(render=True)
    else:
        while simulation_app.is_running():
            world.step(render=True)

    simulation_app.close()


if __name__ == "__main__":
    main()
