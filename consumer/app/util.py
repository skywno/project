import os
import logging

logger = logging.getLogger(__name__)

def get_env_boolean(env_var_name, default_value=False):
    """
    Retrieves an environment variable and converts its string value to a boolean.

    Recognizes 'true', '1', 'on', 'yes' (case-insensitive) as True.
    Recognizes 'false', '0', 'off', 'no' (case-insensitive) as False.
    For any other value, or if the environment variable is not set,
    it returns the specified default_value.

    Args:
        env_var_name (str): The name of the environment variable.
        default_value (bool): The boolean value to return if the
                              environment variable is not set or
                              cannot be interpreted as a boolean.

    Returns:
        bool: The converted boolean value or the default_value.
    """
    env_value = os.getenv(env_var_name)

    if env_value is None:
        return default_value
    
    # Convert to lowercase for case-insensitive comparison
    env_value_lower = env_value.lower()

    if env_value_lower in ('true', '1', 'on', 'yes'):
        return True
    elif env_value_lower in ('false', '0', 'off', 'no'):
        return False
    else:
        # Log a warning if the value is unexpected but still return default
        print(f"Warning: Environment variable '{env_var_name}' has an unrecognized boolean value '{env_value}'. Using default '{default_value}'.")
        return default_value


def get_env_int(env_var_name, default_value=0):
    """
    Retrieves an environment variable and converts its string value to an integer.

    Args:
        env_var_name (str): The name of the environment variable.
        default_value (int): The integer value to return if the
                              environment variable is not set or
                              cannot be interpreted as an integer.

    Returns:
        int: The converted integer value or the default_value.
    """
    env_value = os.getenv(env_var_name)

    if env_value is None:
        return default_value
    
    try:
        return int(env_value)
    except ValueError:
        print(f"Warning: Environment variable '{env_var_name}' has an unrecognized integer value '{env_value}'. Using default '{default_value}'.")
        return default_value
