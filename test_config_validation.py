import toml
from pathlib import Path

config_path = Path("/Users/dariapavlova/Documents/vendor_ai_agent/.streamlit/config.toml")

print("=" * 60)
print("Streamlit Config Validation")
print("=" * 60)

if config_path.exists():
    print(f"✅ Config file exists: {config_path}")
    
    with open(config_path, "r") as f:
        config = toml.load(f)
    
    print("\n📄 Config contents:")
    for section, values in config.items():
        print(f"\n[{section}]")
        for key, value in values.items():
            print(f"  {key} = {value}")
    
    print("\n" + "=" * 60)
    print("⏱️  Session Timeout Settings")
    print("=" * 60)
    
    client_config = config.get("client", {})
    
    print(f"\n📋 All available sections: {list(config.keys())}")
    print(f"📋 Client config keys: {list(client_config.keys())}")
    
    print("\n⚠️  NOTE: sessionIdleTimeout is NOT in the config!")
    print("   This means we need to add it manually.")
    
else:
    print(f"❌ Config file NOT FOUND: {config_path}")
    print("   Streamlit will use default settings (10 min timeout)")

print("\n" + "=" * 60)
