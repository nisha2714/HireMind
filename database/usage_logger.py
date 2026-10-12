"""Usage logging for all LLM calls."""

import uuid
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.db_manager import DBManager


class UsageLogger:
    """Log all LLM API calls and their costs."""

    @staticmethod
    def log_usage(
        agent_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        cost_usd: float,
        interview_id: str = None,
        user_id: str = None,
        status: str = "success",
        error_message: str = None,
    ):
        """
        Log an LLM API call.

        Args:
            agent_name: Name of the agent (e.g., 'ScorerAgent', 'RecommenderAgent')
            model: Model used (e.g., 'gpt-4o-mini')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            latency_ms: Latency in milliseconds
            cost_usd: Estimated cost in USD
            interview_id: ID of the interview (optional)
            user_id: ID of the user (optional)
            status: 'success' or 'error'
            error_message: Error message if status is 'error'
        """
        try:
            db = DBManager()
            log_id = str(uuid.uuid4())
            conn = db._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO usage_logs
                (id, timestamp, user_id, interview_id, agent_name, model_used,
                 input_tokens, output_tokens, latency_ms, cost_usd, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    datetime.now().isoformat(),
                    user_id or "system",
                    interview_id,
                    agent_name,
                    model,
                    input_tokens,
                    output_tokens,
                    latency_ms,
                    cost_usd,
                    status,
                    error_message,
                )
            )
            conn.commit()
            conn.close()

            return log_id

        except Exception as e:
            print(f"Error logging usage: {e}")
            return None

    @staticmethod
    def get_usage_stats(interview_id: str = None):
        """Get usage statistics."""
        try:
            db = DBManager()
            conn = db._get_connection()
            cursor = conn.cursor()

            if interview_id:
                cursor.execute(
                    """
                    SELECT
                        agent_name,
                        COUNT(*) as call_count,
                        SUM(input_tokens) as total_input,
                        SUM(output_tokens) as total_output,
                        AVG(latency_ms) as avg_latency,
                        SUM(cost_usd) as total_cost
                    FROM usage_logs
                    WHERE interview_id = ?
                    GROUP BY agent_name
                    """,
                    (interview_id,)
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        agent_name,
                        COUNT(*) as call_count,
                        SUM(input_tokens) as total_input,
                        SUM(output_tokens) as total_output,
                        AVG(latency_ms) as avg_latency,
                        SUM(cost_usd) as total_cost
                    FROM usage_logs
                    GROUP BY agent_name
                    """
                )

            results = cursor.fetchall()
            conn.close()
            return results

        except Exception as e:
            print(f"Error getting usage stats: {e}")
            return []

    @staticmethod
    def get_cost_breakdown(interview_id: str = None):
        """Get cost breakdown by agent."""
        try:
            db = DBManager()
            conn = db._get_connection()
            cursor = conn.cursor()

            if interview_id:
                cursor.execute(
                    """
                    SELECT
                        agent_name,
                        ROUND(SUM(cost_usd), 4) as total_cost,
                        COUNT(*) as num_calls
                    FROM usage_logs
                    WHERE interview_id = ?
                    GROUP BY agent_name
                    ORDER BY total_cost DESC
                    """,
                    (interview_id,)
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        agent_name,
                        ROUND(SUM(cost_usd), 4) as total_cost,
                        COUNT(*) as num_calls
                    FROM usage_logs
                    GROUP BY agent_name
                    ORDER BY total_cost DESC
                    """
                )

            results = cursor.fetchall()
            conn.close()
            return results

        except Exception as e:
            print(f"Error getting cost breakdown: {e}")
            return []
