from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from polyester_bot.config import Settings
from polyester_bot.logging import configure_logging

def main():
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    print(f"configuration valid: environment={settings.environment}, symbol={settings.symbol}, live={settings.enable_live_trading}")
    if settings.enable_live_trading:
        print("WARNING: live order execution is enabled; this check does not place an order")

if __name__ == '__main__': main()
