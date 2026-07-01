import streamlit as str_web

def zaaplikuj_stylizacje():
    str_web.markdown("""
        <style>
        .stButton>button { 
            background-color: #E31B23 !important; 
            color: #FFFFFF !important; 
            font-weight: bold !important;
            font-size: 16px !important;
            border: none !important;
            border-radius: 4px !important;
            border-right: 8px solid #F39200 !important;
            padding: 10px 24px !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        }
        .stButton>button:hover { background-color: #C61219 !important; }
        div[data-testid="stNotification"] {
            background-color: rgba(46, 204, 113, 0.15) !important;
            border-left: 5px solid #2ECC71 !important;
        }
        div[data-testid="stDataFrame"] { border-radius: 6px !important; }
        </style>
    """, unsafe_allow_html=True)