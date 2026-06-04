# DWR Copy/Paste Permit Workflow (2026)

This note lists the scripts used to clean and reconcile permit data copied from DWR-facing tables/files.

## 1) Reconcile Permit Columns (all non-Expo/Conservation rows)

Script:

- `scripts/reconcile-all-species-permits-2026.py`

What it does:

- normalizes pasted permit text like `Res:`, `NonRes:`, `Total:`
- moves/deletes blank continuation rows where non-resident values were pasted on a second line
- calculates total when `res + nr` exists and total is blank
- reconciles permit fields against canonical 2026 database truth
- excludes Expo/Conservation rows by default

Run:

```powershell
python scripts/reconcile-all-species-permits-2026.py --target-csv "C:\Users\tyler\Desktop\species truth data\2026 deer doe.csv" --write
```

Optional to include Expo/Conservation in the same pass:

```powershell
python scripts/reconcile-all-species-permits-2026.py --target-csv "<your file>.csv" --include-special --write
```

## 2) Reconcile Expo + Conservation Hunt-Type/Hunt-Class/Hunt-Code

Script:

- `scripts/reconcile-expo-conservation-rows.py`

What it does:

- confirms Expo/Conservation rows using database + conservation match table
- fills missing `hunt_code` when confident
- applies:
  - conservation -> `hunt_type=conservation` (+ organization in `hunt_class` when available)
  - expo -> `hunt_type=L.E.` and `hunt_class=expo`

Run:

```powershell
python scripts/reconcile-expo-conservation-rows.py --target-csv "C:\Users\tyler\Desktop\species truth data\2026 deer buck db.csv" --write
```

## 3) Deer-Only Conservation Reconcile (targeted)

Script:

- `scripts/reconcile-deer-conservation-rows.py`

What it does:

- deer conservation-only targeted pass
- confirms conservation rows and sets `hunt_type=conservation`
- fills organizations into `hunt_class` where present
- fills missing `hunt_code` when confident

Run:

```powershell
python scripts/reconcile-deer-conservation-rows.py --target-csv "C:\Users\tyler\Desktop\species truth data\2026 deer buck db.csv" --write
```

## 4) Deer Draw-Class Standardization Rules

Script:

- `scripts/apply-deer-buck-drawclass-rules.py`

What it does:

- applies draw-class keywords consistently:
  - `sportsman` -> `hunt_type=L.E.` + `hunt_class=sportsmens` + total permits = `1`
  - `conservation` -> `hunt_type=conservation`
  - `expo` -> `hunt_type=L.E.` + `hunt_class=expo` (if not conservation)
  - `private` -> `hunt_type=L.E.` + `hunt_class=private only`

Run:

```powershell
python scripts/apply-deer-buck-drawclass-rules.py --csv "C:\Users\tyler\Desktop\species truth data\2026 deer buck db.csv" --write
```

## Recommended Sequence

1. `reconcile-all-species-permits-2026.py`
2. `reconcile-expo-conservation-rows.py`
3. `reconcile-deer-conservation-rows.py` (if deer file needs targeted lock)
4. `apply-deer-buck-drawclass-rules.py` (if deer draw-class cleanup is needed)

