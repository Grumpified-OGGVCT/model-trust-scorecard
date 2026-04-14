"""
SQLite persistence for model evaluations with optional HuggingFace Dataset export.

The storage layer is deliberately simple:
  - One table (evaluations) storing JSON blobs of ModelEvaluation records
  - Indexed by model_id + evaluated_at for fast lookup
  - Optional export to HF Dataset for community sharing

This design keeps the core engine dependency-light while still supporting
reproducible audit trails.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from trust_scorecard.models import ModelEvaluation

logger = logging.getLogger(__name__)


class EvaluationStore:
    """SQLite-backed store for model evaluations."""

    def __init__(self, db_path: str | Path = "trust_scores.db"):
        """
        Initialize the evaluation store.

        Parameters
        ----------
        db_path:
            Path to the SQLite database file. Created if it doesn't exist.
        """
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Create the evaluations table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL,
                    trust_score REAL,
                    data TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(model_id, evaluated_at)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_id
                ON evaluations(model_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_evaluated_at
                ON evaluations(evaluated_at DESC)
            """)
            conn.commit()
        logger.info("Initialized database at %s", self.db_path)

    def save(self, evaluation: ModelEvaluation) -> None:
        """
        Save a model evaluation to the database.

        If an evaluation for the same model_id and evaluated_at already exists,
        it will be replaced.

        Parameters
        ----------
        evaluation:
            The evaluation record to save.
        """
        data_json = evaluation.model_dump_json(indent=2)
        trust_score = evaluation.trust_score.score if evaluation.trust_score else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluations
                (model_id, evaluated_at, trust_score, data)
                VALUES (?, ?, ?, ?)
                """,
                (
                    evaluation.model_id,
                    evaluation.evaluated_at.isoformat(),
                    trust_score,
                    data_json,
                ),
            )
            conn.commit()
        logger.info(
            "Saved evaluation for %s (score: %.1f)",
            evaluation.model_id,
            trust_score or 0.0,
        )

    def get_latest(self, model_id: str) -> Optional[ModelEvaluation]:
        """
        Retrieve the most recent evaluation for a given model.

        Parameters
        ----------
        model_id:
            The model identifier to look up.

        Returns
        -------
        The latest ModelEvaluation record, or None if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT data FROM evaluations
                WHERE model_id = ?
                ORDER BY evaluated_at DESC
                LIMIT 1
                """,
                (model_id,),
            )
            row = cursor.fetchone()
            if row:
                return ModelEvaluation.model_validate_json(row[0])
        return None

    def get_all_latest(self) -> list[ModelEvaluation]:
        """
        Retrieve the most recent evaluation for each model.

        Returns
        -------
        A list of ModelEvaluation records, one per model, ordered by trust score
        descending.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT data FROM evaluations e1
                WHERE evaluated_at = (
                    SELECT MAX(evaluated_at)
                    FROM evaluations e2
                    WHERE e2.model_id = e1.model_id
                )
                ORDER BY trust_score DESC NULLS LAST
            """)
            return [ModelEvaluation.model_validate_json(row[0]) for row in cursor.fetchall()]

    def get_history(self, model_id: str, limit: int = 10) -> list[ModelEvaluation]:
        """
        Retrieve evaluation history for a model.

        Parameters
        ----------
        model_id:
            The model identifier.
        limit:
            Maximum number of historical records to return.

        Returns
        -------
        A list of ModelEvaluation records ordered by evaluated_at descending.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT data FROM evaluations
                WHERE model_id = ?
                ORDER BY evaluated_at DESC
                LIMIT ?
                """,
                (model_id, limit),
            )
            return [ModelEvaluation.model_validate_json(row[0]) for row in cursor.fetchall()]

    def export_to_json(self, output_path: str | Path) -> None:
        """
        Export all latest evaluations to a JSON file.

        Parameters
        ----------
        output_path:
            Path to write the JSON file.
        """
        evaluations = self.get_all_latest()
        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "count": len(evaluations),
            "evaluations": [e.model_dump(mode="json") for e in evaluations],
        }
        output_path = Path(output_path)
        output_path.write_text(json.dumps(data, indent=2))
        logger.info("Exported %d evaluations to %s", len(evaluations), output_path)

    def export_to_hf_dataset(
        self,
        dataset_name: str,
        token: Optional[str] = None,
        private: bool = False,
    ) -> str:
        """
        Export all latest evaluations to a Hugging Face Dataset.

        Requires the 'datasets' library to be installed (install with [hf] extra).

        Parameters
        ----------
        dataset_name:
            HuggingFace dataset identifier (e.g., 'my-org/trust-scores')
        token:
            HuggingFace API token. If None, uses HF_TOKEN env var.
        private:
            Whether to create a private dataset.

        Returns
        -------
        The URL of the published dataset.

        Raises
        ------
        ImportError:
            If the datasets library is not installed.
        """
        try:
            from datasets import Dataset
        except ImportError as exc:
            raise ImportError(
                "HuggingFace datasets library not installed. "
                "Install with: pip install trust-scorecard[hf]"
            ) from exc

        evaluations = self.get_all_latest()
        records = [e.model_dump(mode="json") for e in evaluations]

        dataset = Dataset.from_list(records)
        dataset.push_to_hub(
            dataset_name,
            token=token,
            private=private,
        )

        url = f"https://huggingface.co/datasets/{dataset_name}"
        logger.info("Published %d evaluations to %s", len(records), url)
        return url
