# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import random
import string
import time

import carb
from pxr import PhysxSchema
from pxr import Gf, Usd, UsdGeom, UsdSkel, UsdPhysics
import omni.usd
import omni.anim.navigation.core as nav
import AnimGraphSchema
from omni.metropolis.utils.usd_util import USDUtil
from omni.metropolis.utils.simulation_util import SimulationUtil
from omni.anim.people_api.scripts.interactable_object_helper import InteractableObjectHelper
from omni.anim.people_api.settings import PeopleSettings


class Utils:
    """
    Class provides utility functions and also stores config variables for character actions.
    """

    """
    ------------------------Config Variables------------------------
    """

    CONFIG = {
        "SecondPerNightyDegreeTurn": 0.15,  # 0.25
        "MinDistanceToFinalTarget": 0.15,  # 0.35   # Not in use
        "MinDistanceToIntermediateTarget": 0.25,  # 0.45
        "WalkBlendTime": 0.2,
        "DistanceToOccupyQueueSpot": 1.5,
        "TalkDistance": 1.5,
    }

    """
    ------------------------Utilities Functions for Characters------------------------
    """

    def get_character_transform(c):
        pos = carb.Float3(0, 0, 0)
        rot = carb.Float4(0, 0, 0, 0)
        c.get_world_transform(pos, rot)
        return pos, rot

    def get_character_pos(c):
        pos, rot = Utils.get_character_transform(c)
        return pos

    def get_character_rot(c):
        pos, rot = Utils.get_character_transform(c)
        return rot

    """
    ------------------------Other Utilities Functions------------------------
    """

    def rotZ3(v, d):
        rotYMat = Gf.Matrix3d(Gf.Rotation(Gf.Vec3d(0, 0, 1), d))
        vRot = Gf.Vec3d(v.x, v.y, v.z) * rotYMat
        return carb.Float3(vRot[0], vRot[1], vRot[2])

    def convert_to_angle(quat_rot):
        rot_in_angle = Gf.Rotation(Gf.Quatd(quat_rot.w, quat_rot.x, quat_rot.y, quat_rot.z))
        zaxis = rot_in_angle.GetAxis()[2]
        rot_angle = rot_in_angle.GetAngle()
        if zaxis < 0:
            rot_angle = -rot_angle
        return rot_angle

    def is_character(prim_path):
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path)
        if prim.IsA(UsdSkel.Root) and prim.HasAPI(AnimGraphSchema.AnimationGraphAPI):
            return True
        else:
            return False

    def convert_angle_to_quatd(z_angle):
        rotation = None
        if z_angle < 0:
            rotation = Gf.Rotation(Gf.Vec3d(0, 0, -1), -z_angle)
        else:
            rotation = Gf.Rotation(Gf.Vec3d(0, 0, 1), z_angle)
        quat_value = rotation.GetQuat()
        imaginary = quat_value.GetImaginary()
        real = quat_value.GetReal()
        return carb.Float4(imaginary[0], imaginary[1], imaginary[2], real)

    def get_object_radius(prim_path):
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path)
        box_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), includedPurposes=[UsdGeom.Tokens.default_])
        bound = box_cache.ComputeWorldBound(prim)
        range = bound.ComputeAlignedBox()
        bboxMin = range.GetMin()
        bboxMax = range.GetMax()
        bbox_x = bboxMax[0] - bboxMin[0]
        bbox_y = bboxMax[1] - bboxMin[1]
        radius = max(bbox_y, bbox_x)
        return radius / 2

    """
    ------------------------Interactable Prims------------------------
    """

    def calc_path_to_interactable_prim(character, prim):
        start_point = Utils.get_character_pos(character)
        prim_trans, prim_rot = USDUtil.USDUtil.get_prim_pos_and_rot(prim=prim)
        walk_to_offset, interact_offset = InteractableObjectHelper.get_interactable_prim_attributes(prim)
        offset = walk_to_offset
        # convert offset according to prim's rotation
        offset = offset * Gf.Matrix3d(prim_rot)
        end_point = carb.Float3(prim_trans[0] + offset[0], prim_trans[1] + offset[1], prim_trans[2] + offset[2])
        gf_quat = prim_rot.GetQuat()
        gf_i = gf_quat.GetImaginary()
        end_rot = carb.Float4(gf_i[0], gf_i[1], gf_i[2], gf_quat.GetReal())
        return (start_point, end_point, end_rot)

    def calc_interact_world_position(prim):
        prim_trans, prim_rot = USDUtil.get_prim_pos_and_rot(prim=prim)
        walk_to_offset, interact_offset = InteractableObjectHelper.get_interactable_prim_attributes(prim)
        anim_offset = interact_offset
        # convert offset according to prim's rotation
        anim_offset = anim_offset * Gf.Matrix3d(prim_rot)
        return carb.Float3(
            prim_trans[0] + anim_offset[0], prim_trans[1] + anim_offset[1], prim_trans[2] + anim_offset[2]
        )

    """
    ------------------------NavMesh------------------------
    """

    def accessible_navmesh_point(character_position, point):
        carb.log_warn("Called")
        navmesh = nav.acquire_interface().get_navmesh()
        character_point = carb.Float3(character_position[0], character_position[1], character_position[2])
        target_point = carb.Float3(point[0], point[1], point[2])
        # then query the closet navigation point toward the target point:
        cloest_point_raw = navmesh.query_closest_point(target_point, agent_radius=0.5)[0]
        cloest_point = carb.Float3(cloest_point_raw[0], cloest_point_raw[1], cloest_point_raw[2])
        # check whether two point are really close:
        if not SimulationUtil.is_the_same_point(target_point, cloest_point, tol=0.1):
            # if the point is not accessible at all
            return False
        nav_path = navmesh.query_shortest_path(character_point, cloest_point, agent_radius=0.5)
        carb.log_warn("finished accessible navmesh point")
        if (not nav_path) or (not nav_path.get_points()):
            return False
        return True

    def get_closest_navmesh_point(point):
        """check whether a point is on navmesh"""
        navmesh = nav.acquire_interface().get_navmesh()
        closest_point = navmesh.query_closest_point(carb.Float3(point[0], point[1], point[2]), agent_radius=0.5)[0]
        return closest_point

    def get_navmesh_area_index(area_name):
        """fetch navmesh area index"""
        navigation_interface = nav.acquire_interface()
        index = navigation_interface.find_area(area_name)
        return index

    def get_accessible_point_within_area(area_name, random_id=None, character_position=None, max_attempts=100):
        """get accessible point within the area"""
        navigation_interface = nav.acquire_interface()
        navmesh = navigation_interface.get_navmesh()
        target_index = navigation_interface.find_area(area_name)
        total_area_count = navigation_interface.get_area_count()
        index_list = [0] * total_area_count
        index_list[target_index] = 1
        if random_id is None:
            random_id = "Default_Random_Id"

        accessible = False
        attempt = 0
        randomized_point = None
        while (not accessible) and attempt < max_attempts:
            randomized_point = navmesh.query_random_point(random_id, index_list)
            carb.log_warn("query randomized point within navmesh area" + str(randomized_point))
            if character_position is not None:
                accessible = Utils.accessible_navmesh_point(
                    point=randomized_point, character_position=character_position
                )
            else:
                accessible = True
            if not accessible:
                randomized_point = None

        return randomized_point

    def get_closest_accessible_point(target_prim, character_pos):
        """check whether the prim is accessible by the character"""
        object_pos_raw = omni.usd.get_world_transform_matrix(target_prim).ExtractTranslation()
        object_pos = carb.Float3(object_pos_raw[0], object_pos_raw[1], 0)
        destination_pos = Utils.get_closest_navmesh_point(object_pos)
        carb.log_warn("This is the closest point" + str(destination_pos))
        if not SimulationUtil.is_the_same_point(object_pos, destination_pos, 1.5):
            carb.log_warn("no point nearby")
            return None
        if not Utils.accessible_navmesh_point(point=destination_pos, character_position=character_pos):
            return None
        return destination_pos

    """
    ----------------------Command--------------------------
    """

    def generate_unique_id(character_name="", prefix="CMD", length=8):
        """Generates a unique ID for commands"""
        timestamp = int(time.time() * 1000)
        random_str = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
        unique_id = f"{character_name}-{prefix}-{timestamp}-{random_str}"
        return unique_id

    def check_command_type(cmd):
        """Check command type, whether command has an id"""
        if isinstance(cmd, str):
            return "string"
        elif isinstance(cmd, tuple) and len(cmd) == 2:
            return "pair"
        else:
            return "unknown"

    """
    -----------------------Agent------------------------------------
    """

    def fetch_target_character_path_by_name(character_name: str):
        """fetch the skeleton path that we can used to fetch target character instance in the stage"""
        stage = omni.usd.get_context().get_stage()
        character_root_path = carb.settings.get_settings().get(PeopleSettings.CHARACTER_PRIM_PATH)
        folder_prim = stage.GetPrimAtPath(character_root_path)
        if not folder_prim.IsValid() or not folder_prim.IsActive():
            return None

        target_character_prim = None
        children = folder_prim.GetAllChildren()
        for character_prim in children:
            if UsdGeom.Imageable(character_prim).ComputeVisibility() == UsdGeom.Tokens.invisible:
                continue
            if str(character_prim.GetName()) == character_name:
                target_character_prim = character_prim

        if target_character_prim is None:
            return None

        # after we fetch the target character prim, fetch the skeleton pirm path

        for prim in Usd.PrimRange(target_character_prim):
            if prim.GetTypeName() == "SkelRoot":
                return prim.GetPrimPath()

        return None

    def fetch_target_character_instance_by_name(character_name: str):
        target_character_skelroot_path = Utils.fetch_target_character_path_by_name(character_name)
        return SimulationUtil.get_agent_script_instance_by_path(target_character_skelroot_path)

    def get_character_position_by_name(character_name):
        """fetch target character's position via character name"""
        character_instance = Utils.fetch_target_character_instance_by_name(character_name)
        if character_instance is None:
            carb.log_warn(
                "cannot find target character {character_name}, fail to inject command".format(
                    character_name=character_name
                )
            )
            return
        character_position = character_instance.get_current_position()
        return character_position

    def is_agent_task_interruptable(character_name):
        """check whether character status is interactable"""
        character_instance = Utils.fetch_target_character_instance_by_name(character_name)
        if character_instance is None:
            carb.log_warn(
                "cannot find target character {character_name}, fail to inject command".format(
                    character_name=character_name
                )
            )
            return
        character_status = character_instance.check_interruptable()
        return character_status

    def runtime_inject_command(
        character_name: str, command_list: list, force_inject: bool = True, set_status: bool = True
    ):
        """inject command to the character ether focreful or at the end of the queue"""
        character_instance = Utils.fetch_target_character_instance_by_name(character_name)
        if character_instance is None:
            carb.log_warn(
                "cannot find target character {character_name}, fail to inject command".format(
                    character_name=character_name
                )
            )
            return

        if force_inject:
            character_instance.end_current_command(set_status)

        character_instance.inject_command(command_list=command_list, executeImmediately=force_inject)

    """
    -----------------------Custom Added Utils(not in omni.anim.people)------------------------------------
    """

    # From the functionality of isaacsim.replicator.behavior.utils,
    # modified to work with omni.anim.people_api.scripts.utils.py

    # Enables collisions with the asset (without rigid body dynamics the asset will be static)
    def add_colliders(root_prim):
        trigger_state_api_list = []
        # Iterate descendant prims (including root) and add colliders to mesh or primitive types
        for desc_prim in Usd.PrimRange(root_prim):
            if desc_prim.IsA(UsdGeom.Mesh) or desc_prim.IsA(UsdGeom.Gprim):
                # desc_prim.CreatePurposeAttr(UsdGeom.Tokens.guide)
                # Physics
                if not desc_prim.HasAPI(UsdPhysics.CollisionAPI):
                    collision_api = UsdPhysics.CollisionAPI.Apply(desc_prim)
                else:
                    collision_api = UsdPhysics.CollisionAPI(desc_prim)
                collision_api.CreateCollisionEnabledAttr(True)
                # PhysX
                if not desc_prim.HasAPI(PhysxSchema.PhysxCollisionAPI):
                    physx_collision_api = PhysxSchema.PhysxCollisionAPI.Apply(desc_prim)
                else:
                    physx_collision_api = PhysxSchema.PhysxCollisionAPI(desc_prim)
                # Set PhysX specific properties
                physx_collision_api.CreateContactOffsetAttr(0.001)
                physx_collision_api.CreateRestOffsetAttr(0.0)

                # Add mesh specific collision properties only to mesh types
                if desc_prim.IsA(UsdGeom.Mesh):
                    # Add mesh collision properties to the mesh (e.g. collider aproximation type)
                    if not desc_prim.HasAPI(UsdPhysics.MeshCollisionAPI):
                        mesh_collision_api = UsdPhysics.MeshCollisionAPI.Apply(desc_prim)
                    else:
                        mesh_collision_api = UsdPhysics.MeshCollisionAPI(desc_prim)
                    mesh_collision_api.CreateApproximationAttr().Set(UsdPhysics.Tokens.convexDecomposition)

                # Add trigger to the prim
                if not desc_prim.HasAPI(PhysxSchema.PhysxTriggerAPI):
                    PhysxSchema.PhysxTriggerAPI.Apply(desc_prim)
                if not desc_prim.HasAPI(PhysxSchema.PhysxTriggerStateAPI):
                    trigger_state_api = PhysxSchema.PhysxTriggerStateAPI.Apply(desc_prim)
                else:
                    trigger_state_api = PhysxSchema.PhysxTriggerStateAPI(desc_prim)
                trigger_state_api_list.append(trigger_state_api)
        return trigger_state_api_list

    # Enables rigid body dynamics (physics simulation) on the prim
    def add_rigid_body_dynamics(prim, disable_gravity=False, angular_damping=None):
        # Physics
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            rigid_body_api = UsdPhysics.RigidBodyAPI.Apply(prim)
        else:
            rigid_body_api = UsdPhysics.RigidBodyAPI(prim)
        rigid_body_api.CreateRigidBodyEnabledAttr(True)
        rigid_body_api.CreateKinematicEnabledAttr(True)
        # PhysX
        if not prim.HasAPI(PhysxSchema.PhysxRigidBodyAPI):
            physx_rigid_body_api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        else:
            physx_rigid_body_api = PhysxSchema.PhysxRigidBodyAPI(prim)
        physx_rigid_body_api.GetDisableGravityAttr().Set(disable_gravity)
        if angular_damping is not None:
            physx_rigid_body_api.CreateAngularDampingAttr().Set(angular_damping)
