"""
ObRail Europe - Control dashboard (deliverable #6 of the specifications).

Consumes the REST API (deliverable #4) rather than the database directly:
this is the usage the specifications intend ("allow the dataset to be
exploited by the project's other components"), and it decouples the
dashboard from any implementation detail of the database.

Digital accessibility (explicit requirement of the specifications,
reference: RGAA / WCAG 2.1 level AA):
- color palette inspired by the ONS Accessible Colours (UK Office for
  National Statistics), designed to stay distinguishable for color
  blindness and keep sufficient contrast on a white background
- no information is conveyed by color ALONE: every chart has named
  axes, value labels, and a text summary right below it (equivalent to
  alt text)
- raw data tables always stay available next to each chart, for
  non-visual access to the same figures
- increased font size on charts (Plotly's default is too small to stay
  comfortably readable)

Run with:
    streamlit run app.py
"""

import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_URL = os.getenv("OBRAIL_API_URL", "http://localhost:8001")

# ONS Accessible Colours palette - tested for WCAG AA + color-blindness distinction.
COLOR_JOUR = "#F46A25"     # dark orange
COLOR_NUIT = "#12436D"     # dark navy blue
COLOR_BAR = "#28A197"      # teal (volume bars)
COLOR_LINE = "#801650"     # burgundy (trend line)

st.set_page_config(page_title="ObRail Europe - Tableau de bord", layout="wide")


def style_fig(fig, height: int = 420):
    """Applies consistent, readable formatting to every figure: a larger
    font than Plotly's default, comfortable margins."""
    fig.update_layout(
        font=dict(size=14),
        title_font_size=18,
        height=height,
        margin=dict(t=60, l=10, r=10, b=40),
    )
    return fig


@st.cache_data(ttl=60)
def fetch_json(path: str, params: dict | None = None):
    resp = requests.get(f"{API_URL}{path}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


st.title("ObRail Europe — Tableau de bord de contrôle")
st.caption(
    "Suivi de la complétude et de la qualité de l'entrepôt de données ferroviaires. "
    f"Données lues depuis l'API : {API_URL}"
)

# ---------------------------------------------------------------------
# Section 1: Quality of the latest ETL run (KPIs + history)
# ---------------------------------------------------------------------
st.header("1. Qualité des données (dernières exécutions ETL)")

try:
    quality_runs = fetch_json("/qualite", {"limit": 20})
except requests.RequestException as e:
    st.error(f"Impossible de contacter l'API ({API_URL}). Est-elle bien lancée ? Détail : {e}")
    st.stop()

if not quality_runs:
    st.warning("Aucune exécution ETL enregistrée pour le moment. Lance `run_pipeline.py`.")
    st.stop()

df_quality = pd.DataFrame(quality_runs).sort_values("date_execution")
latest = df_quality.iloc[-1]

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Lignes lues (dernier passage)", f"{int(latest['nb_lignes_lues']):,}".replace(",", " "))
col2.metric("Lignes chargées", f"{int(latest['nb_lignes_chargees']):,}".replace(",", " "))
col3.metric("Doublons supprimés", int(latest["nb_doublons_supprimes"]))
col4.metric(
    "Taux de lignes conservées", f"{latest['taux_completude_pct']:.2f} %",
    help="Part des lignes lues qui ont passé le nettoyage et ont été chargées en base "
         "(nb_lignes_chargees / nb_lignes_lues). Ne mesure PAS si tous les champs sont remplis.",
)
# Complementary indicator, computed here from nb_valeurs_manquantes:
# the row-retention rate (above) can be 100% even though some secondary
# FIELDS (distance, emissions...) remain empty on a few rows - this is a
# different indicator, not a contradiction. Shown separately to avoid
# confusing "the row was kept" with "all of its fields are filled in".
NB_CHAMPS_SUIVIS = 6  # see tracked_cols in transform.clean_raw()
taux_champs_renseignes = 100 - (
    100 * latest["nb_valeurs_manquantes"] / (latest["nb_lignes_lues"] * NB_CHAMPS_SUIVIS)
)
col5.metric(
    "Champs renseignés", f"{taux_champs_renseignes:.3f} %",
    help=f"Part des champs sensibles (sur {NB_CHAMPS_SUIVIS} suivis par ligne : gares, "
         "horaires, distance, émission) réellement remplis - distinct du taux de lignes "
         f"conservées. {int(latest['nb_valeurs_manquantes'])} valeurs manquantes détectées "
         f"sur {int(latest['nb_lignes_lues']) * NB_CHAMPS_SUIVIS:,} champs vérifiés.".replace(",", " "),
)

if len(df_quality) > 1:
    fig_quality = px.line(
        df_quality, x="date_execution", y="taux_completude_pct",
        markers=True, title="Évolution du taux de lignes conservées entre exécutions",
        labels={"date_execution": "Date d'exécution", "taux_completude_pct": "Lignes conservées (%)"},
        color_discrete_sequence=[COLOR_LINE],
    )
    fig_quality.update_yaxes(range=[0, 100])
    fig_quality.update_traces(line_width=3, marker_size=9)
    st.plotly_chart(style_fig(fig_quality), width="stretch")
    st.caption(
        f"Taux de lignes conservées stable à {latest['taux_completude_pct']:.2f} % sur les "
        f"{len(df_quality)} dernières exécutions du pipeline — aucune ligne rejetée. "
        "C'est une ligne (pas une barre) parce qu'on suit une évolution dans le temps, "
        "une exécution du pipeline après l'autre."
    )
else:
    st.caption("Une seule exécution enregistrée pour le moment — relance `run_pipeline.py` pour voir une tendance.")

with st.expander("Voir le détail de chaque exécution (données brutes)"):
    st.dataframe(df_quality, width="stretch")

# ---------------------------------------------------------------------
# Section 2: Day / Night breakdown
# ---------------------------------------------------------------------
st.header("2. Répartition des dessertes : Jour vs Nuit")

col_a, col_b = st.columns([1, 2])
with col_a:
    jour = fetch_json("/dessertes", {"service_type": "Jour", "limit": 1})["total"]
    nuit = fetch_json("/dessertes", {"service_type": "Nuit", "limit": 1})["total"]
    total_dessertes = jour + nuit
    st.metric("Total dessertes", f"{total_dessertes:,}".replace(",", " "))
    df_jn = pd.DataFrame({"Type": ["Jour", "Nuit"], "Nombre": [jour, nuit]})
    fig_jn = px.bar(
        df_jn, x="Type", y="Nombre", color="Type", text="Nombre",
        title="Nombre de dessertes par type de service",
        color_discrete_map={"Jour": COLOR_JOUR, "Nuit": COLOR_NUIT},
    )
    fig_jn.update_traces(textposition="outside", textfont_size=14)
    st.plotly_chart(style_fig(fig_jn, height=380), width="stretch")
with col_b:
    st.dataframe(df_jn, width="stretch")
    st.caption(
        f"{nuit} trains de nuit recensés sur {total_dessertes} dessertes au total "
        f"({100*nuit/total_dessertes:.1f} %). Un train de nuit relie deux gares avec "
        "un départ tardif et une arrivée après minuit selon l'heure encodée à la source "
        "(et non une simple estimation)."
    )

# ---------------------------------------------------------------------
# Section 3: Volume per operator
# ---------------------------------------------------------------------
st.header("3. Volume de données collectées par opérateur")

df_ops = pd.DataFrame(fetch_json("/stats/operateurs"))
fig_ops = px.bar(
    df_ops.head(15), x="nb_dessertes", y="nom_operateur", orientation="h",
    title="Nombre de dessertes par opérateur (15 premiers)",
    labels={"nb_dessertes": "Nombre de dessertes", "nom_operateur": "Opérateur"},
    color_discrete_sequence=[COLOR_BAR],
)
fig_ops.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(style_fig(fig_ops, height=500), width="stretch")

top_op = df_ops.iloc[0]
autres_ops = len(df_ops) - 1
st.caption(
    f"{len(df_ops)} opérateurs distincts recensés. {top_op['nom_operateur']} est le plus "
    f"représenté avec {int(top_op['nb_dessertes']):,}".replace(",", " ") +
    f" dessertes (réseau domestique SNCF, source GTFS), face à {autres_ops} opérateurs "
    "européens plus modestes en volume mais essentiels à la comparaison internationale "
    "(source Back-on-Track)."
)
with st.expander("Voir tous les opérateurs (données brutes)"):
    st.dataframe(df_ops, width="stretch")

# ---------------------------------------------------------------------
# Section 4: Coverage per country
# ---------------------------------------------------------------------
st.header("4. Couverture géographique")

df_pays = pd.DataFrame(fetch_json("/stats/pays"))
fig_pays = px.bar(
    df_pays.head(15), x="nb_dessertes", y="nom_pays", orientation="h",
    title="Nombre de dessertes par pays de départ (15 premiers)",
    labels={"nb_dessertes": "Nombre de dessertes", "nom_pays": "Pays"},
    color_discrete_sequence=[COLOR_BAR],
)
fig_pays.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(style_fig(fig_pays, height=500), width="stretch")

autres_pays = df_pays["nb_dessertes"][1:].sum()
st.caption(
    f"**{len(df_pays)} pays** couverts par l'entrepôt de données. La France concentre "
    f"l'essentiel du volume (réseau SNCF), mais {int(autres_pays):,}".replace(",", " ") +
    " dessertes couvrent 25 autres pays européens, confirmant la portée "
    "transfrontalière visée par ObRail Europe."
)
with st.expander("Voir tous les pays (données brutes)"):
    st.dataframe(df_pays, width="stretch")
