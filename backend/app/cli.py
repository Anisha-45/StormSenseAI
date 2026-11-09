"""Command-line helpers.
  python -m app.cli process                       # build the processed event table from data/raw
  python -m app.cli create-admin EMAIL NAME PASS  # create the first administrator
  python -m app.cli demo-experiments              # run one hierarchical and one DBSCAN experiment
"""
import json
import sys

from .db import database as db


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    db.init_db()
    cmd = argv[0]
    if cmd == "process":
        from .services import processing
        m = processing.process()
        print(json.dumps({k: m[k] for k in ("unique_events", "events_with_coordinates", "year_counts", "processing_seconds")}, indent=2))
        for i in m["issues"]:
            print(f"- [{i['table']}] {i['issue']}: {i['count']}")
        return 0
    if cmd == "create-admin" and len(argv) == 4:
        from .core import security as S
        with db.session() as con:
            if db.one(con, "SELECT id FROM users WHERE email=?", (argv[1].lower(),)):
                print("User already exists.")
                return 1
            problems = S.validate_password(argv[3])
            if problems:
                print(" ".join(problems))
                return 1
            con.execute("INSERT INTO users(email,name,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                        (argv[1].lower(), argv[2], S.hash_password(argv[3]), "administrator", db.now()))
        print("Administrator created.")
        return 0
    if cmd == "demo-experiments":
        from .services import experiments as E
        a = E.run_experiment("hierarchical", {"n_clusters": 6, "linkage": "ward"}, {"sample_size": 5000})
        b = E.run_experiment("dbscan", {"min_samples": 10}, {"sample_size": 5000}, with_stability=True)
        print("hierarchical experiment", a["experiment_id"], "| dbscan experiment", b["experiment_id"])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
