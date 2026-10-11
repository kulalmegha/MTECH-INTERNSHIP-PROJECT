from pathlib import Path
import sys

# Forwarding stub to root scripts/seed_demo.py
ROOT_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "seed_demo.py"
if str(ROOT_SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT_SCRIPT.parent))

if __name__ == "__main__":
    import asyncio
    from seed_demo import seed_demo
    asyncio.run(seed_demo())
