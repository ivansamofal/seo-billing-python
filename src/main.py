#!/usr/bin/env python3
"""

SEO Billing CLI

Usage:
    python -m src.main update-balance [--date YYYY-MM-DD]
"""

import logging
import sys
from typing import Optional

import click

from src.config.database import SessionLocal
from src.domain.pricing.tariff_pricing_strategy import TariffPricingStrategy
from src.services.billing_service import BillingService
from src.services.external_api_service import ExternalApiService


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command("update-balance")
@click.option(
    "--date",
    default=None,
    metavar="YYYY-MM-DD",
    help="Billing date (defaults to today)",
)
@click.pass_context
def update_balance(ctx: click.Context, date: Optional[str]) -> None:
    logger = logging.getLogger(__name__)

    session = SessionLocal()
    try:
        external_api = ExternalApiService()
        pricing = TariffPricingStrategy()
        billing = BillingService(session, external_api, pricing)

        result = billing.process_write_off(date)

        logger.info(
            "Billing completed: date=%s, users_charged=%d, total_amount=%d rubles",
            result.date, result.processed_users, result.total_amount,
        )
        click.echo(
            f"Done: {result.processed_users} users charged, "
            f"{result.total_amount} rubles on {result.date}"
        )
    except Exception as exc:
        logger.error("Billing failed: %s", exc, exc_info=True)
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    cli()
