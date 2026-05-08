def get_current_weather(location: str, unit: str = "celsius") -> str:
    """
    Gets the current weather for a given location.

    Args:
        location: The city and state, e.g. San Francisco, CA
        unit: The temperature unit ('celsius' or 'fahrenheit').
    """
    return f"The weather in {location} is 22 degrees {unit} and sunny."
