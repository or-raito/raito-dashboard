"""
One-shot patch: fix pistachio product record in master_data table.
Run from Cloud Shell:
  DATABASE_URL="postgresql://raito_app:raito_app@127.0.0.1:5432/raito" python3 patch_pistachio.py
"""
import os, json, psycopg2

url = os.environ['DATABASE_URL']
conn = psycopg2.connect(url)
cur = conn.cursor()

# Read current products
cur.execute("SELECT data FROM master_data WHERE entity = 'products'")
row = cur.fetchone()
if not row:
    print("ERROR: no products row in master_data")
    exit(1)

products = row[0]  # psycopg2 auto-decodes JSONB
print(f"Found {len(products)} products")

# Find and patch pistachio
patched = False
for p in products:
    sku = p.get('sku_key') or p.get('sku') or ''
    if sku == 'pistachio':
        print(f"Before: {p}")
        # Rename brand_key → brand, manufacturer_key → manufacturer
        if 'brand_key' in p:
            p['brand'] = p.pop('brand_key')
        if 'manufacturer_key' in p:
            p['manufacturer'] = p.pop('manufacturer_key')
        # Set correct values if still blank
        if not p.get('brand'):
            p['brand'] = 'turbo'
        if not p.get('manufacturer'):
            p['manufacturer'] = 'vaniglia'
        print(f"After:  {p}")
        patched = True

if not patched:
    print("ERROR: pistachio not found in products list")
    print("SKU keys present:", [p.get('sku_key') for p in products])
    exit(1)

# Write back
cur.execute("""
    INSERT INTO master_data (entity, data, updated_at)
    VALUES ('products', %s, NOW())
    ON CONFLICT (entity) DO UPDATE
        SET data = EXCLUDED.data, updated_at = NOW()
""", (json.dumps(products),))
conn.commit()
conn.close()
print("Done — pistachio patched successfully.")
