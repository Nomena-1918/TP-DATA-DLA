"""Configuration et fabriques de connexions aux bases de données."""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
import mysql.connector
from mysql.connector.connection import MySQLConnection
import psycopg
from psycopg import Connection

# Recherche du fichier .env à la racine du projet TP
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
if ENV_PATH.is_file():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()


def exiger_acces(variable: str, ancienne_variable: str) -> str:
    valeur = os.getenv(variable) or os.getenv(ancienne_variable)
    if not valeur:
        raise RuntimeError(f"Variable requise : {variable}.")
    return valeur


def verrouiller_ecritures_etl(cur) -> None:
    """Sérialise les écritures du pipeline et de l’arbitrage dans cette base."""
    cur.execute("SELECT pg_advisory_xact_lock(1414546500);")


def get_auto_config() -> dict:
    """Paramètres de connexion pour la base source Auto (PostgreSQL)."""
    return {
        "host": os.getenv("TP_AUTO_HOST") or os.getenv("postgres.host", "localhost"),
        "port": int(os.getenv("TP_AUTO_PORT") or os.getenv("postgres.port", "5432")),
        "dbname": os.getenv("TP_AUTO_DB", "tp_assurance_auto"),
        "user": exiger_acces("TP_AUTO_USER", "postgres.user"),
        "password": exiger_acces("TP_AUTO_PASSWORD", "postgres.pwd"),
    }


def get_life_config() -> dict:
    """Paramètres de connexion pour la base source Life (MySQL)."""
    return {
        "host": os.getenv("TP_LIFE_HOST") or os.getenv("my.host", "localhost"),
        "port": int(os.getenv("TP_LIFE_PORT") or os.getenv("my.port", "3306")),
        "database": os.getenv("TP_LIFE_DB", "tp_assurance_life"),
        "user": exiger_acces("TP_LIFE_USER", "my.user"),
        "password": exiger_acces("TP_LIFE_PASSWORD", "my.pwd"),
    }


def get_etl_config() -> dict:
    """Paramètres de connexion pour la base cible ETL (PostgreSQL)."""
    return {
        "host": os.getenv("TP_ETL_HOST") or os.getenv("postgres.host", "localhost"),
        "port": int(os.getenv("TP_ETL_PORT") or os.getenv("postgres.port", "5432")),
        "dbname": os.getenv("TP_ETL_DB", "tp_assurance_etl"),
        "user": exiger_acces("TP_ETL_USER", "postgres.user"),
        "password": exiger_acces("TP_ETL_PASSWORD", "postgres.pwd"),
    }


@contextmanager
def get_auto_connection() -> Generator[Connection, None, None]:
    """Ouvre une connexion PostgreSQL en lecture seule sur Auto."""
    cfg = get_auto_config()
    with psycopg.connect(**cfg) as conn:
        conn.read_only = True
        yield conn


@contextmanager
def get_life_connection() -> Generator[MySQLConnection, None, None]:
    """Ouvre une connexion MySQL en lecture seule sur Life."""
    cfg = get_life_config()
    conn = mysql.connector.connect(**cfg, charset="utf8mb4")
    try:
        conn.start_transaction(readonly=True)
        yield conn
    finally:
        conn.close()


@contextmanager
def get_etl_connection() -> Generator[Connection, None, None]:
    """Ouvre une connexion PostgreSQL en écriture sur tp_assurance_etl."""
    cfg = get_etl_config()
    with psycopg.connect(**cfg) as conn:
        yield conn
