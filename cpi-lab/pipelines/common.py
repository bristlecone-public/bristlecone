"""Shared config for the CPI lab."""
import os, sqlite3, time, hashlib, logging, requests, pathlib

ROOT = pathlib.Path(os.environ.get("CPI_ROOT", "./cpi-data"))
RAW = ROOT / "raw"
OUT = ROOT / "out"
DB = ROOT / "cpi.db"
UA = "cpilab/0.1 (+https://github.com/bristlecone-public/bristlecone)"
BLS_TS = "https://download.bls.gov/pub/time.series/"

for d in (RAW, OUT):
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cpi")

_s = requests.Session()
_s.headers["User-Agent"] = UA


def fetch(url, dest: pathlib.Path, force=False, retries=3):
    """Download url to dest unless unchanged (HEAD Last-Modified check). Returns (path, changed)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    stamp = dest.with_suffix(dest.suffix + ".lm")
    old_lm = stamp.read_text().strip() if stamp.exists() else None
    for i in range(retries):
        try:
            h = _s.head(url, timeout=60, allow_redirects=True)
            lm = h.headers.get("Last-Modified")
            if not force and dest.exists() and lm and lm == old_lm:
                return dest, False
            r = _s.get(url, timeout=600)
            r.raise_for_status()
            dest.write_bytes(r.content)
            if lm:
                stamp.write_text(lm)
            log.info("fetched %s (%d bytes)", url, len(r.content))
            return dest, True
        except Exception as e:  # noqa
            log.warning("fetch %s failed (%s), retry %d", url, e, i + 1)
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"could not fetch {url}")


def db():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS pulls(pull_id INTEGER PRIMARY KEY, pulled_at TEXT, source TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS cu_item(item_code TEXT PRIMARY KEY, item_name TEXT, display_level INT, selectable TEXT, sort_sequence INT, parent_code TEXT);
CREATE TABLE IF NOT EXISTS cu_series(series_id TEXT PRIMARY KEY, area_code TEXT, item_code TEXT, seasonal TEXT, periodicity_code TEXT, base_code TEXT, base_period TEXT, series_title TEXT, begin_year INT, begin_period TEXT, end_year INT, end_period TEXT);
-- one row per (series, month, value) vintage; latest = max(pull_id)
CREATE TABLE IF NOT EXISTS cpi_obs(series_id TEXT, year INT, period TEXT, value REAL, footnote TEXT, pull_id INT, PRIMARY KEY(series_id, year, period, pull_id));
CREATE INDEX IF NOT EXISTS cpi_obs_sp ON cpi_obs(series_id, year, period);
CREATE VIEW IF NOT EXISTS cpi_obs_latest AS
  SELECT o.series_id, o.year, o.period, o.value, o.footnote, o.pull_id FROM cpi_obs o
  JOIN (SELECT series_id, year, period, MAX(pull_id) pull_id FROM cpi_obs GROUP BY 1,2,3) m USING(series_id, year, period, pull_id);
CREATE TABLE IF NOT EXISTS cpi_weight(weight_year INT, item_code TEXT, item_name TEXT, weight_u REAL, weight_w REAL, matched INT, section TEXT, level INT, is_leaf INT, PRIMARY KEY(weight_year, item_code));
CREATE TABLE IF NOT EXISTS cpi_item_month(item_code TEXT, ym TEXT, idx_nsa REAL, idx_sa REAL, mom_sa REAL, mom_nsa REAL, yoy REAL, ann3m REAL, weight REAL, contrib_yoy REAL, PRIMARY KEY(item_code, ym));
CREATE TABLE IF NOT EXISTS validation(run_at TEXT, check_name TEXT, ym TEXT, ours REAL, published REAL, diff REAL, ok INT);
"""


def init_db():
    con = db()
    con.executescript(SCHEMA)
    con.commit()
    return con


def new_pull(con, source, note=""):
    cur = con.execute("INSERT INTO pulls(pulled_at, source, note) VALUES(datetime('now'),?,?)", (source, note))
    return cur.lastrowid
