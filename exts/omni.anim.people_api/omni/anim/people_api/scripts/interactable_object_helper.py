from pxr import Sdf, Gf, Usd
import carb
import omni.usd
from omni.metropolis.utils.type_util import TypeUtil
from omni.metropolis.utils.usd_util import USDUtil


class InteractableObjectTags:
    interact_action = ("InteractableObjectTags_Interactable_Action", Sdf.ValueTypeNames.String)
    interact_type = ("InteractableObjectTags_Interactable_Type", Sdf.ValueTypeNames.String)
    owners = ("InteractableObjectTags_Owners", Sdf.ValueTypeNames.StringArray)

    @classmethod
    def __getattr__(cls, name):
        """Return the formatted string and the actual type when accessing attributes directly."""
        if name in cls.__dict__:
            # Returns the tuple (formatted string, type) directly
            return cls.__dict__[name]
        else:
            raise AttributeError(f"{name} is not a valid attribute of {cls.__name__}")

    @classmethod
    def get_all_tags(cls) -> list:
        """Return all attributes in the formatted string and their types as a list of tuples."""
        return [
            (value[0], value[1])
            for name, value in cls.__dict__.items()
            if not name.startswith("__") and not callable(getattr(cls, name))
        ]

    @classmethod
    def has_tag(cls, target_name):
        """Check if target_name is a class variable in InteractableObjectTags."""
        return target_name in cls.__dict__


class Interactable_Type:
    single_access = "single_access"
    multi_access = "multi_access"


class InteractableObjectHelper:
    def is_object_interactable(target_prim, allow_vanila_interact=True):
        """check the states of interactable object"""
        owners_property, _ = InteractableObjectTags.owners
        interact_type_property, _ = InteractableObjectTags.interact_type
        # if the object do not have interaction_type/_action/_owner attached on it
        if not target_prim.HasAttribute(interact_type_property):
            # check whether we can do vanila interact
            # carb.log_info("vanila interaction, no status checking")
            return allow_vanila_interact
        # get the owner of current object
        owners: list = []
        owners_value = target_prim.GetAttribute(owners_property).Get()
        if owners_value:
            owners = list(owners_value)
        # get the type of current interactable objects
        interact_type = str(target_prim.GetAttribute(interact_type_property).Get())
        # check whether there are to much owner for certain object.
        if interact_type == Interactable_Type.single_access:
            return len(owners) == 0
        return True

    def remove_owner(target_prim, agent_name):
        owners_property, _ = InteractableObjectTags.owners
        # if the object do not have interaction_type/_action/_owner attached on it
        if not target_prim.HasAttribute(owners_property):
            # check whether we can do vanila interact
            # carb.log_info("vanila interaction, no status update")
            return
        # get the owner of current object
        owners: list = []
        owners_value = target_prim.GetAttribute(owners_property).Get()
        if owners_value:
            owners = list(owners_value)
        # udpate the owner list
        if agent_name in owners:
            owners.remove(agent_name)
            target_prim.GetAttribute(owners_property).Set(owners)

    def add_owner(target_prim, agent_name):
        owners_property, _ = InteractableObjectTags.owners
        # if the object do not have interaction_type/_action/_owner attached on it
        if not target_prim.HasAttribute(owners_property):
            # check whether we can do vanila interact
            return
        # get the owner of current object
        owners: list = []
        owners_value = target_prim.GetAttribute(owners_property).Get()
        if owners_value:
            owners = list(owners_value)
        # update the owner list
        if agent_name not in owners:
            owners.append(agent_name)
            target_prim.GetAttribute(owners_property).Set(owners)

    def get_all_interactable_objects_in_stage(root_prim_path: str = ""):
        result = []
        stage = omni.usd.get_context().get_stage()
        root_prim = None
        if not (root_prim_path and stage.GetPrimAtPath(root_prim_path).IsValid()):
            root_prim = stage.GetDefaultPrim()
        else:
            root_prim = stage.GetPrimAtPath(root_prim_path)
        for prim in Usd.PrimRange(root_prim):
            if InteractableObjectHelper.is_object_interactable(prim):
                result.append(prim)
        return result

    def get_interact_prim_offsets(stage, prim):
        prim_path = prim.GetPrimPath()
        # walk_to_offset
        walk_to_offset_prim = stage.GetPrimAtPath(f"{prim_path}/walk_to_offset")
        if not walk_to_offset_prim.IsValid():
            carb.log_info(f"No 'walk_to_offset' under prim '{prim_path}', will use prim's transform instead.")
            walk_to_offset_prim = prim
        walk_to_pos, walk_to_rot = USDUtil.get_prim_pos_and_rot(prim=walk_to_offset_prim)
        walk_to_pos[2] = 0
        walk_to_pos = TypeUtil.gf_vec3_to_carb_float3(walk_to_pos)
        walk_to_rot = TypeUtil.gf_quatd_to_carb_float4(walk_to_rot.GetQuat())
        # interact_offset
        interact_offset_prim = stage.GetPrimAtPath(f"{prim_path}/interact_offset")
        if not interact_offset_prim.IsValid():
            carb.log_info(f"No 'interact_offset' under prim '{prim_path}', will use walk_to_offset instead.")
            interact_offset_prim = walk_to_offset_prim
        interact_pos, interact_rot = USDUtil.get_prim_pos_and_rot(prim=interact_offset_prim)
        interact_pos = TypeUtil.gf_vec3_to_carb_float3(interact_pos)
        interact_rot = TypeUtil.gf_quatd_to_carb_float4(interact_rot.GetQuat())
        return walk_to_pos, walk_to_rot, interact_pos, interact_rot

    def get_interactable_prim_attributes(prim):
        walk_to_offset = Gf.Vec3d(0, 0, 0)
        if not prim.HasAttribute("walk_to_offset"):
            carb.log_warn(f"No walk_to_offset attribute on prim {prim.GetPrimPath()}, (0,0,0) will be used instead.")
        else:
            walk_to_offset = prim.GetAttribute("walk_to_offset").Get()
        interact_offset = Gf.Vec3d(0, 0, 0)
        if not prim.HasAttribute("interact_offset"):
            carb.log_warn(f"No interact_offset attribute on prim {prim.GetPrimPath()}, (0,0,0) will be used instead.")
        else:
            interact_offset = prim.GetAttribute("interact_offset").Get()
        return walk_to_offset, interact_offset
