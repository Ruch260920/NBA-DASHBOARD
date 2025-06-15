import streamlit as st
import pandas as pd
from google.cloud import storage
import io
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import re
from collections import Counter
from html import escape
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


st.set_page_config(page_title="🏀 NBA Reddit Insights", layout="wide", page_icon="🏀")
st.markdown("""
    <style>
        .block-container {padding-top: 1.3rem !important;}
        header[data-testid="stHeader"] {height: 0px; min-height: 0px; visibility: hidden;}
        .main {background: linear-gradient(135deg,#fff6e7 0,#ffe1f0 100%)!important;}
        .kpi-card {background:#fff;border-radius:20px;box-shadow:0 4px 32px rgba(0,0,0,0.10);padding:32px;text-align:center;margin-bottom:12px;}
        .kpi-header {font-size:18px;letter-spacing:1px;color:#9333ea;margin-bottom:8px;}
        .kpi-value {font-size:38px;font-weight:700;color:#111;}
        .emoji {font-size:30px;margin-bottom:0px;}
        .smalltext {font-size:13px;color:#888;}
        .sent-pos {color:#22c55e; font-weight:700;}
        .sent-neg {color:#ef4444; font-weight:700;}
        .sent-neu {color:#64748b; font-weight:700;}
        table td, table th {font-size: 1.04rem !important;}
    </style>
""", unsafe_allow_html=True)

with st.container():
    st.markdown("<h1 style='font-size: 2.5rem; color: #831843; text-align: left;'>🏀 NBA Reddit Dashboard <span style='font-size:1.2rem;color:#f59e42'>Player Insights</span></h1>", unsafe_allow_html=True)


def extract_player_names(titles):
    pattern = re.compile(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b')
    names = []
    for t in titles:
        names += pattern.findall(str(t))
    return [n for n, cnt in Counter(names).items() if cnt >= 2]

def get_sentiment(text, analyzer):
    score = analyzer.polarity_scores(str(text))['compound']
    if score > 0.2:
        return 'Positive'
    elif score < -0.2:
        return 'Negative'
    else:
        return 'Neutral'


st.sidebar.header("🔎 Filter & Explore")
BUCKET_NAME = "nba-reddit-data-2025-ruchi"

@st.cache_data(show_spinner=True)
def list_csv_files(bucket_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    files = [blob.name for blob in bucket.list_blobs() if blob.name.endswith('.csv')]
    return sorted(files, reverse=True)

@st.cache_data(show_spinner=True)
def load_csv_from_gcs(bucket_name, blob_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    data = blob.download_as_bytes()
    df = pd.read_csv(io.BytesIO(data))
    return df

files = list_csv_files(BUCKET_NAME)
if not files:
    st.warning("No data files found in bucket!")
    st.stop()
selected_file = st.sidebar.selectbox("Select NBA Reddit data file:", files)
df = load_csv_from_gcs(BUCKET_NAME, selected_file)
st.sidebar.markdown(f"<span class='smalltext'>Loaded {len(df)} posts</span>", unsafe_allow_html=True)


player_names = extract_player_names(df['title'])
player_names = sorted(player_names)
selected_player = st.sidebar.selectbox("Filter by Player Name", ["All Players"] + player_names)
score_filter = st.sidebar.slider("Minimum Upvotes", min_value=0, max_value=1000, value=0, step=10)


df = df[df['score'] >= score_filter]
if selected_player and selected_player != "All Players":
    player_df = df[df['title'].str.contains(selected_player, case=False, na=False)]
else:
    player_df = df
if player_df.empty:
    st.warning("No posts match your filter. Try different player or lower upvote filter.")
    st.stop()

player_df['created_utc'] = pd.to_datetime(player_df['created_utc'])
player_df = player_df.sort_values('created_utc', ascending=False)


analyzer = SentimentIntensityAnalyzer()
player_df['sentiment'] = player_df['title'].apply(lambda x: get_sentiment(x, analyzer))


col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("<div class='kpi-card'><div class='emoji'>📝</div><div class='kpi-header'>Posts</div><div class='kpi-value'>{}</div></div>".format(len(player_df)), unsafe_allow_html=True)
with col2:
    st.markdown("<div class='kpi-card'><div class='emoji'>💬</div><div class='kpi-header'>Avg Comments</div><div class='kpi-value'>{:.0f}</div></div>".format(player_df['num_comments'].mean()), unsafe_allow_html=True)
with col3:
    st.markdown("<div class='kpi-card'><div class='emoji'>👍</div><div class='kpi-header'>Avg Upvotes</div><div class='kpi-value'>{:.0f}</div></div>".format(player_df['score'].mean()), unsafe_allow_html=True)

st.subheader(f"🔥 Top 10 Posts{' for ' + selected_player if selected_player != 'All Players' else ''}")

top10 = player_df.sort_values('score', ascending=False).head(10).copy()

def sentiment_html(sent):
    if sent == "Positive":
        return "<span class='sent-pos'>Positive</span>"
    elif sent == "Negative":
        return "<span class='sent-neg'>Negative</span>"
    else:
        return "<span class='sent-neu'>Neutral</span>"

top10['Title'] = top10.apply(lambda row: f"<a href='{row['url']}' target='_blank'>{escape(str(row['title']))}</a>", axis=1)
top10['Sentiment_html'] = top10['sentiment'].apply(sentiment_html)
top10['Date'] = top10['created_utc'].dt.strftime('%Y-%m-%d %H:%M')
table_disp = top10[['Title', 'score', 'num_comments', 'Sentiment_html', 'Date']]
table_disp = table_disp.rename(columns={'score': 'Upvotes', 'num_comments': 'Comments', 'Sentiment_html': 'Sentiment'})

st.markdown(
    table_disp.to_html(escape=False, index=False), 
    unsafe_allow_html=True
)
sent_counts = player_df['sentiment'].value_counts().reindex(['Positive','Neutral','Negative']).fillna(0)
fig_s = px.bar(
    x=sent_counts.index, 
    y=sent_counts.values, 
    color=sent_counts.index, 
    color_discrete_map={'Positive':'#22c55e', 'Neutral':'#64748b', 'Negative':'#ef4444'},
    labels={'x':'Sentiment','y':'Number of Posts'},
    title="Sentiment Distribution"
)
fig_s.update_layout(showlegend=False)
st.plotly_chart(fig_s, use_container_width=True)
c1, c2 = st.columns([1.3,0.7])
with c1:
    st.subheader("📈 Upvotes Distribution")
    fig = px.histogram(player_df, x='score', nbins=30, color_discrete_sequence=["#8b5cf6"])
    fig.update_layout(xaxis_title="Upvotes", yaxis_title="Number of Posts", plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📅 Posts Over Time")
    time_counts = player_df.set_index('created_utc').resample('6H').size()
    fig2 = px.area(time_counts, labels={'index':'Date','value':'Posts'}, color_discrete_sequence=["#38bdf8"])
    fig2.update_traces(mode="lines+markers")
    fig2.update_layout(xaxis_title="Date", yaxis_title="Posts", plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

with c2:
    st.subheader("☁️ Wordcloud")
    wc = WordCloud(width=360, height=260, background_color='white', colormap='inferno').generate(' '.join(player_df['title'].astype(str)))
    figwc, ax = plt.subplots(figsize=(4,3))
    ax.imshow(wc, interpolation='bilinear')
    ax.axis("off")
    st.pyplot(figwc, use_container_width=True)
st.markdown("<div style='text-align:right;font-size:12px;color:#aaa;margin-top:30px;'>Made with ❤️ for NBA Lovers</div>", unsafe_allow_html=True)
