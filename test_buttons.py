from signal import pause

try:
    from gpiozero import Button
except Exception as exc:
    raise SystemExit(
        "gpiozero could not be imported. Make sure your environment has access "
        f"to the Raspberry Pi GPIO packages.\nOriginal error: {exc}"
    ) from exc


GPIO_PINS = {
    "up": 17,
    "down": 18,
    "left": 27,
    "right": 23,
    "quit": 24,
}


def main():
    buttons = {}

    try:
        for name, pin in GPIO_PINS.items():
            button = Button(pin, pull_up=false, bounce_time=0.05)
            button.when_pressed = lambda button_name=name: print(f"{button_name}: pressed")
            button.when_released = lambda button_name=name: print(f"{button_name}: released")
            buttons[name] = button
    except Exception as exc:
        raise SystemExit(
            "Failed to initialize GPIO buttons.\n"
            "If you are using uv on Raspberry Pi OS, recreate the venv with "
            "`uv venv --system-site-packages`, install `python3-lgpio`, and run with "
            "`GPIOZERO_PIN_FACTORY=lgpio`.\n"
            f"Original error: {exc}"
        ) from exc

    print("Listening for button events on BCM pins:")
    for name, pin in GPIO_PINS.items():
        print(f"  {name}: GPIO {pin}")
    print("Press Ctrl+C to stop.")

    pause()


if __name__ == "__main__":
    main()
