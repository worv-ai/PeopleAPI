from typing import Any, get_origin

import carb


def get_inner_type(typ) -> tuple:
    """Get the inner type(s) of a type variable."""
    # Check if the type has inner types (using `__args__`)
    if hasattr(typ, "__args__"):
        return typ.__args__
    return ()


def cast_to_type(value: Any, target_type: type) -> Any | None:
    """
    Try to cast `value` to `target_type`.
    If successful, return the casted value.
    If not, return `None`.
    """
    try:
        # Handle `list[type]` or nested lists
        if (target_type is list or get_origin(target_type) is list) and isinstance(value, list):
            # Assuming `target_type` is `list[float]` (or nested lists)
            # This function should be defined elsewhere
            inner_type_tuple = get_inner_type(target_type)

            if len(inner_type_tuple) == 0:
                return None

            inner_type = inner_type_tuple[0]
            casted_list = []

            for item in value:
                # If item is a list, apply the function recursively
                if isinstance(item, list):
                    casted_item = cast_to_type(item, inner_type)
                    if casted_item is None:
                        return None
                    casted_list.append(casted_item)
                else:
                    casted_item = inner_type(item)
                    casted_list.append(casted_item)

            return casted_list

        else:
            # Directly cast `value` to `target_type`
            return target_type(value)
    except (ValueError, TypeError):
        return None


def can_cast_to_type(value: Any, target_type: type) -> bool:
    return cast_to_type(value=value, target_type=target_type) is not None


class CommandParamter:
    """Record data for each command parameter"""

    def __init__(
        self,
        name: str,
        param_type: type,
        length: int = 1,
        description: str = "",
        optional: bool = False,
        constant_match: bool = False,
        example_input: Any = None,
        special_value: tuple | None = None,
    ):
        # place holder name of this parameter, would be shown when showing command format
        self.name: str = name
        self.length: int = length
        self.param_type: type = param_type
        self.description: str = description
        self.constant_match: bool = (
            constant_match  # True if this command parameter is the command name, like "GoTo", "Idle"
        )
        self.optional: bool = optional  # True if the parameter is optional
        self.example_parameter = example_input
        self.special_value = None
        if special_value and isinstance(special_value, tuple) and len(special_value) == 3:
            # record the special value and type of this parameter
            self.special_value = special_value

    def get_normal_parameter(self, parsed_command: Any) -> Any:
        """check whether the input command is correct"""
        target_input = parsed_command
        if isinstance(parsed_command, list) and len(parsed_command) == 1 and get_origin(self.param_type) is not list:
            target_input = parsed_command[0]
        normal_case = cast_to_type(value=target_input, target_type=self.param_type)
        if isinstance(normal_case, list):
            print("list element type " + str(type(normal_case[0])))

        return normal_case

    def get_special_parameter(self, parsed_command: Any) -> Any:
        target_input = parsed_command
        # Fix the `len(parsed_command) == 0`(which is original one in omni.anim.people-0.7.9+107.3.3)
        # to `len(parsed_command) == 1`
        if isinstance(parsed_command, list) and len(parsed_command) == 1 and get_origin(self.param_type) is not list:
            target_input = parsed_command[0]
        target_type, target_value, target_length = self.special_value
        if can_cast_to_type(value=target_input, target_type=target_type):
            if target_type(parsed_command) == target_value:
                return target_value
        return None

    def collect_info(self):
        result = {"name": self.name, "length": self.length, "example_input": self.example_parameter}
        return result


class CommandFormatHelper:
    """Helper class to generate command instruction in a more scalable way"""

    parameters_info: list[CommandParamter] = []
    command_defined = False  # Flag to check if parameters are defined
    parameter_defined = False
    # variable that record command description
    command_description: str | None = None
    command_usage: Any = None  # the usecase of this command

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Automatically override class variables in the subclass
        cls.parameters_info: list[CommandParamter] = []
        cls.command_defined = False
        cls.parameter_defined = False
        cls.command_description = None
        cls.command_usage = None

    @classmethod
    def define_all_parameters(cls):
        """define the placeholder, type and explaination"""
        cls.parameter_defined = True
        pass

    @classmethod
    def _ensure_command_defined(cls):
        """Ensure parameters are defined only once, on demand."""
        if not cls.parameter_defined:
            cls.define_all_parameters()
        if not cls.command_defined:
            cls.set_command_description_usage()

    @classmethod
    def define_parameter(
        cls,
        name: str,
        param_type: type,
        length: int = 1,
        description: str = "",
        optional: bool = False,
        constant_match: bool = False,
        example_input: Any = None,
        special_value: tuple | None = None,
    ):
        """define the parameter, add the parameter to the list"""
        cls.parameters_info.append(
            CommandParamter(
                name=name,
                param_type=param_type,
                length=length,
                description=description,
                optional=optional,
                constant_match=constant_match,
                example_input=example_input,
                special_value=special_value,
            )
        )

    @classmethod
    def set_command_description_usage(cls):
        """define the command description"""
        # Place holder to define the command description.
        cls.command_defined = True
        pass

    @classmethod
    def get_command_usage(cls):
        """get the usage of the command"""
        return cls.command_usage

    @classmethod
    def get_command_description(cls):
        """get semantic description of this command"""
        return cls.command_description

    @classmethod
    def collect_parameters_info(cls) -> str:
        """collect all command parameter information in the command"""
        cls._ensure_command_defined()
        parameter_dict: dict[str, Any] = {}
        for parameter in cls.parameters_info:
            parameter_dict["Name"] = parameter.name
            parameter_dict["Type"] = parameter.param_type
            parameter_dict["Description"] = parameter.description
            parameter_dict["Is_Optional"] = parameter.optional
            parameter_dict["Example Parameter"] = parameter.example_parameter
            parameter_dict["Special Value"] = parameter.special_value
        return parameter_dict

    @classmethod
    def generate_template_command(cls) -> str:
        cls._ensure_command_defined()
        """generate a string that show command format"""
        result_list = []
        for parameter in cls.parameters_info:
            parameter_name = parameter.name
            result_list.append(parameter_name)
        output_str = " ".join(map(str, result_list))
        return output_str

    @classmethod
    def generate_example_command(cls) -> str:
        cls._ensure_command_defined()
        """generate a string that show command format"""
        result_list = []
        for parameter in cls.parameters_info:
            place_holder = None
            if (not parameter.constant_match) and parameter.example_parameter:
                place_holder = parameter.example_parameter
            else:
                place_holder = parameter.name
            if isinstance(place_holder, list):
                result_list.extend(place_holder)
            else:
                result_list.append(place_holder)
        output_str = " ".join(map(str, result_list))
        return output_str

    @classmethod
    def validate_command_format(cls, command: list[str] | str) -> dict[str, Any] | None:
        """
        Check whether the input command string follows the correct format.

        :param command_str: The command string to validate.
        :return: True if the format is correct, False otherwise.
        """
        # Define the regex pattern based on expected template
        # TODO : check whether the command is a valid command.
        cls._ensure_command_defined()
        command_list = []
        parameter_dict: dict[str, Any] = {}
        if isinstance(command, str):
            command_list = command.strip().split()

        else:
            command_list = command

        command_len = len(command_list)
        parameter_len = len(cls.parameters_info)
        input_index = 0
        parameter_index = 0

        for parameter_info in cls.parameters_info:
            carb.log_info(str(parameter_info.collect_info()))

        carb.log_warn("Input command List" + str(command_list))

        if (not cls.parameters_info) or (not command_list):
            return False

        while input_index < command_len and parameter_index < parameter_len:
            # carb.log_warn(
            #     "This is the parameter info " + str(cls.parameters_info) + " parameter index " + str(parameter_index)
            # )
            parameter = cls.parameters_info[parameter_index]
            parameter_length = parameter.length
            normal_parameter = parameter.get_normal_parameter(
                command_list[input_index: input_index + parameter_length]
            )

            if normal_parameter is not None:
                input_index += parameter_length
                parameter_index += 1
                parameter_dict[parameter.name] = normal_parameter
                continue
            carb.log_info(
                "target parameter name {parameter_name} fail to match with {input_value}".format(
                    parameter_name=str(parameter.name),
                    input_value=str(command_list[input_index: input_index + parameter_length]),
                )
            )

            if parameter.special_value:
                target_type, special_value, special_index_length = parameter.special_value
                special_parameter = parameter.get_special_parameter(  # noqa: F841
                    command_list[input_index: input_index + special_index_length]
                )
                input_index += special_index_length
                parameter_index += 1
                parameter_dict[parameter.name] = special_value
                continue

            if parameter.optional:
                parameter_index += 1
                parameter_dict[parameter.name] = None
                continue

            return None

        # if parameters are missing
        if parameter_index < parameter_len:
            carb.log_warn("parameter missing")
            # check whether all missing parameter is optional
            for command_parameter in cls.parameters_info[parameter_index: parameter_len]:
                if not command_parameter.optional:
                    carb.log_warn("missing parameter" + str(parameter.name))
                    return None

        # check whether there are too many index in the input
        if input_index < command_len:
            carb.log_warn("too many index : command len" + str(command_len) + " input index " + str(input_index))
            return None

        carb.log_warn("The parameter dict" + str(parameter_dict))

        return parameter_dict
