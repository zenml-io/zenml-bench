# sampling

Daily QA sampling pipeline `qa_sampling` (`run.py`): `load_events` reads the event log (slow; a warehouse query in production), `sample_events` draws `n` random events, `review_report` summarises them for the review team. `python run.py --n 50` from this directory. `make_data.py` regenerates `data/events.csv`.
