
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# ==================================================
# BRITISH AIRWAYS CUSTOMER SATISFACTION DASHBOARD
# ==================================================

st.set_page_config(
    page_title="British Airways Analytics",
    page_icon="✈️",
    layout="wide"
)

# ---------------- CUSTOM DESIGN ----------------

st.markdown("""
<style>
.stApp {
    background-color: #f4f7fb;
}
h1, h2, h3 {
    color: #102b50;
}
[data-testid="stMetric"] {
    background: white;
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #d9e2ef;
}
</style>
""", unsafe_allow_html=True)

st.title("✈️ British Airways")
st.subheader("Customer Satisfaction Analytics Dashboard")
st.caption("Passenger reviews • Service ratings • Interactive business insights")

# ---------------- LOAD DATA ----------------

@st.cache_data
def load_data(review_file, country_file):
    reviews = pd.read_csv(review_file)
    countries = pd.read_csv(country_file)

    reviews.columns = reviews.columns.str.strip().str.lower()
    countries.columns = countries.columns.str.strip()

    # Clean text columns
    for col in reviews.select_dtypes(include="object").columns:
        reviews[col] = reviews[col].str.strip()

    # Convert dates
    reviews["date_flown"] = pd.to_datetime(
        reviews["date_flown"], dayfirst=True, errors="coerce"
    )

    # Ratings use -1 for unavailable/not-rated values
    rating_cols = [
        "rating",
        "seat_comfort",
        "cabin_staff_service",
        "food_beverages",
        "ground_service",
        "value_for_money",
        "entertainment"
    ]

    for col in rating_cols:
        if col in reviews.columns:
            reviews[col] = pd.to_numeric(
                reviews[col], errors="coerce"
            )
            reviews.loc[reviews[col] < 0, col] = float("nan")

    # Join the country lookup to add geographical information
    countries.columns = countries.columns.str.strip()
    countries["Country"] = countries["Country"].astype(str).str.strip()

    reviews = reviews.merge(
        countries[["Country", "Code", "Continent", "Region"]],
        left_on="place",
        right_on="Country",
        how="left"
    )

    return reviews


# Default file paths are relative to app.py
review_path = Path(__file__).parent / "ba_reviews.csv"
country_path = Path(__file__).parent / "Countries.csv"

uploaded_reviews = st.sidebar.file_uploader(
    "Upload ba_reviews.csv", type="csv"
)
uploaded_countries = st.sidebar.file_uploader(
    "Upload Countries.csv", type="csv"
)

if uploaded_reviews and uploaded_countries:
    df = load_data(uploaded_reviews, uploaded_countries)
elif review_path.exists() and country_path.exists():
    df = load_data(review_path, country_path)
else:
    st.error(
        "Place both CSV files beside app.py, "
        "or upload both files using the sidebar."
    )
    st.stop()

rating_cols = [
    "rating",
    "seat_comfort",
    "cabin_staff_service",
    "food_beverages",
    "ground_service",
    "value_for_money",
    "entertainment"
]

metric_names = {
    "rating": "Overall Rating",
    "seat_comfort": "Seat Comfort",
    "cabin_staff_service": "Cabin Staff Service",
    "food_beverages": "Food & Beverages",
    "ground_service": "Ground Service",
    "value_for_money": "Value for Money",
    "entertainment": "Entertainment"
}

# ---------------- SIDEBAR FILTERS ----------------

st.sidebar.title("Dashboard Filters")

filtered = df.copy()

def add_filter(column, label):
    global filtered

    if column not in filtered.columns:
        return

    values = sorted(
        filtered[column].dropna().astype(str).unique().tolist()
    )

    selected = st.sidebar.multiselect(
        label,
        values,
        default=values
    )

    filtered = filtered[
        filtered[column].astype(str).isin(selected)
    ]


add_filter("place", "Country")
add_filter("aircraft", "Aircraft")
add_filter("seat_type", "Seat Class")
add_filter("traveller_type", "Traveller Type")
add_filter("recommended", "Recommended")

if "date_flown" in filtered.columns:
    dates = filtered["date_flown"].dropna()

    if not dates.empty:
        start_date = st.sidebar.date_input(
            "Flight date from", value=dates.min().date()
        )
        end_date = st.sidebar.date_input(
            "Flight date to", value=dates.max().date()
        )

        if start_date <= end_date:
            filtered = filtered[
                filtered["date_flown"].isna()
                | (
                    (filtered["date_flown"].dt.date >= start_date)
                    & (filtered["date_flown"].dt.date <= end_date)
                )
            ]
        else:
            st.sidebar.error("Start date must not exceed end date.")

# ---------------- KPI CARDS ----------------

st.markdown("## Key Performance Indicators")

k1, k2, k3, k4 = st.columns(4)

k1.metric("Total Reviews", f"{len(filtered):,}")

average = filtered["rating"].mean()
k2.metric(
    "Average Overall Rating",
    f"{average:.2f} / 5" if pd.notna(average) else "N/A"
)

if "recommended" in filtered.columns:
    rec = filtered["recommended"].str.lower().eq("yes")
    valid_rec = filtered["recommended"].notna()

    rec_rate = (
        rec[valid_rec].mean() * 100
        if valid_rec.any() else float("nan")
    )
    k3.metric(
        "Recommend Rate",
        f"{rec_rate:.1f}%" if pd.notna(rec_rate) else "N/A"
    )
else:
    k3.metric("Recommend Rate", "N/A")

k4.metric(
    "Aircraft Types",
    str(filtered["aircraft"].nunique())
)

st.divider()

# ---------------- SELECT METRIC ----------------

st.markdown("## Passenger Rating Analysis")

selected_metric = st.selectbox(
    "Select a metric",
    rating_cols,
    format_func=lambda x: metric_names[x]
)

left, right = st.columns(2)

# ---------------- AIRCRAFT ANALYSIS ----------------

with left:
    st.markdown("### Average Rating by Aircraft")

    aircraft_data = (
        filtered.groupby("aircraft")[selected_metric]
        .agg(["mean", "count"])
        .reset_index()
        .dropna()
        .sort_values("mean", ascending=False)
    )

    if not aircraft_data.empty:
        fig = px.bar(
            aircraft_data,
            x="aircraft",
            y="mean",
            color="mean",
            hover_data={"count": True},
            color_continuous_scale="Blues",
            labels={
                "aircraft": "Aircraft",
                "mean": "Average Rating",
                "count": "Rated Reviews"
            }
        )
        fig.update_layout(yaxis_range=[0, 5])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No aircraft ratings available for these filters.")

# ---------------- COUNTRY ANALYSIS ----------------

with right:
    st.markdown("### Average Rating by Country")

    country_data = (
        filtered.groupby("place")[selected_metric]
        .agg(["mean", "count"])
        .reset_index()
        .dropna()
        .sort_values("mean", ascending=True)
        .tail(15)
    )

    if not country_data.empty:
        fig = px.bar(
            country_data,
            x="mean",
            y="place",
            orientation="h",
            color="mean",
            hover_data={"count": True},
            color_continuous_scale="Teal",
            labels={
                "place": "Country",
                "mean": "Average Rating",
                "count": "Rated Reviews"
            }
        )
        fig.update_layout(xaxis_range=[0, 5])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No country ratings available.")

# ---------------- MONTHLY TREND ----------------

st.markdown("### Monthly Rating Trend")

trend_data = filtered.dropna(
    subset=["date_flown", selected_metric]
).copy()

if not trend_data.empty:
    trend_data["Month"] = (
        trend_data["date_flown"].dt.to_period("M").dt.to_timestamp()
    )

    trend = (
        trend_data.groupby("Month")[selected_metric]
        .mean()
        .reset_index()
    )

    fig = px.line(
        trend,
        x="Month",
        y=selected_metric,
        markers=True,
        title=f"Monthly {metric_names[selected_metric]}"
    )
    fig.update_layout(yaxis_range=[0, 5])
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No dated ratings available for the selected filters.")

# ---------------- SERVICE COMPARISON ----------------

st.markdown("### Service Quality Comparison")

service_cols = [
    "seat_comfort",
    "cabin_staff_service",
    "food_beverages",
    "ground_service",
    "value_for_money",
    "entertainment"
]

service_summary = pd.DataFrame({
    "Service": [metric_names[c] for c in service_cols],
    "Average Rating": [
        filtered[c].mean() for c in service_cols
    ]
}).dropna()

if not service_summary.empty:
    fig = px.bar(
        service_summary,
        x="Service",
        y="Average Rating",
        color="Average Rating",
        text_auto=".2f",
        color_continuous_scale="Blues"
    )
    fig.update_layout(
        yaxis_range=[0, 5],
        xaxis_tickangle=-25
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------- COUNTRY MAP ----------------

st.markdown("### Global Passenger Satisfaction Map")

map_data = (
    filtered.dropna(subset=["Code", selected_metric])
    .groupby(["Code", "place"])[selected_metric]
    .mean()
    .reset_index()
)

if not map_data.empty:
    fig = px.choropleth(
        map_data,
        locations="Code",
        locationmode="ISO-3",
        color=selected_metric,
        hover_name="place",
        color_continuous_scale="Blues",
        range_color=(0, 5),
        labels={selected_metric: "Average Rating"},
        title=f"Average {metric_names[selected_metric]} by Country"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Country codes or ratings are unavailable for this map.")

# ---------------- REVIEW TABLE ----------------

st.markdown("## Passenger Reviews")

display_cols = [
    c for c in [
        "header", "date", "place", "aircraft",
        "traveller_type", "seat_type", "route",
        "recommended", "rating", "content"
    ] if c in filtered.columns
]

st.dataframe(
    filtered[display_cols],
    use_container_width=True,
    hide_index=True
)

# ---------------- DOWNLOAD ----------------

st.download_button(
    "Download Filtered Reviews",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="ba_filtered_reviews.csv",
    mime="text/csv"
)

st.caption(
    "British Airways Customer Satisfaction Project | "
    "Python • Pandas • Streamlit • Plotly"
)
