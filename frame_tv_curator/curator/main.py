import os, sys, logging, time, signal
from . import config, web
from .engine import Engine
from .mqtt import Entities

def main():
    lvl = config.options().get("log_level", "info").upper()
    logging.basicConfig(level=getattr(logging, lvl, logging.INFO), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    for d in (config.RENDER_DIR, config.EPAPER_DIR):
        os.makedirs(d, exist_ok=True)
    from . import library
    library.ensure_default_folders()
    library.migrate_folder_case()
    eng = Engine()
    config.apply_log_level(eng.settings.get().get("log_level"))
    web.serve(eng, int(os.environ.get("FC_PORT", 8099)))
    if not os.environ.get("FC_NO_MQTT"):
        Entities(eng).start()
    eng.start()
    eng.ambient.start()
    eng.presence.start()
    logging.getLogger("main").info("Frame TV Curator up (dry_run=%s)", eng.dry)
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
