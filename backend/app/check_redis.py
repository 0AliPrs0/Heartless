import redis
import sys

# --- تنظیمات ---
# اگر Redis شما روی هاست یا پورت دیگری است، اینجا تغییر دهید
REDIS_HOST = "localhost"
REDIS_PORT = 6379
# ---------------------

def check_ready_players(game_id: str):
    """به Redis متصل شده و اعضای مجموعه بازیکنان آماده را برای یک بازی مشخص بررسی می‌کند."""
    try:
        # اتصال به Redis
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping() # بررسی موفقیت‌آمیز بودن اتصال
        print(f"Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")

        # ساختن نام کلید، دقیقا مشابه فایل game.py
        ready_players_key = f"game:{game_id}:ready_players"

        # دریافت اعضای مجموعه
        ready_players = r.smembers(ready_players_key)
        num_ready_players = r.scard(ready_players_key)

        print("-" * 30)
        print(f"Querying key: '{ready_players_key}'")
        print(f"Number of ready players found: {num_ready_players}")

        if ready_players:
            print("Ready player IDs:")
            for player_id in ready_players:
                print(f"- {player_id}")
        else:
            print("No ready players found in the set.")
        print("-" * 30)

    except redis.exceptions.ConnectionError as e:
        print(f"Error: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}.")
        print("Please make sure your Redis server is running and the host/port are correct.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # دریافت game_id از آرگومان‌های خط فرمان
    if len(sys.argv) < 2:
        print("Usage: python check_redis.py <game_id>")
        # می‌توانید از game_id موجود در URL مرورگر خود استفاده کنید. در اسکرین‌شات شما، این مقدار 48 بود.
        sys.exit(1)

    game_id_to_check = sys.argv[1]
    check_ready_players(game_id_to_check)
