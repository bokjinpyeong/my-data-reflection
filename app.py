import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from sklearn.neighbors import NearestNeighbors
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from datetime import datetime
import re
from collections import Counter

# -----------------------------------------------------------------------------
# 1. 설정 및 초기화
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="My Data Reflection",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# [핵심] 구글 시트 주소 (secrets.toml 설정 필수)
try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
except Exception:
    st.error("secrets.toml 파일에 구글 시트 URL이 설정되지 않았습니다.")
    st.stop()

# 컬럼 정의
COLS_SUBJECTS = ['경험명', '분야', '내용', 'NFC(탐구욕)', 'NCC(종결욕)', '메모']
COLS_ACTIVITIES = ['경험명', '유형', '내용', 'nAch(성취)', 'nPow(권력)', 'nAff(친화)', '몰입도(Flow)', '메모']
COLS_BOOKS = ['경험명', '통합적복잡성', '의미부여']
COLS_QUESTIONS = ['문항', '소재', '내용'] 


# -----------------------------------------------------------------------------
# 2. 데이터 핸들링
# -----------------------------------------------------------------------------
def get_data(worksheet_name, columns):
    """
    구글 시트에서 데이터를 불러옵니다.
    오류 발생 시 빈 데이터프레임을 반환하여 앱이 멈추지 않도록 합니다.
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        try:
            df = conn.read(worksheet=worksheet_name, ttl=0, spreadsheet=SHEET_URL)
        except TypeError:
            df = conn.read(worksheet=worksheet_name, ttl=0)
        
        # [중요 수정] 컬럼명 공백 제거 (시트 헤더의 실수 방지)
        df.columns = df.columns.str.strip()
        
        # 필수 컬럼이 없으면 생성 (데이터 없는 경우 대비)
        for col in columns:
            if col not in df.columns:
                df[col] = pd.NA
            
        # 숫자 강제 변환 (데이터 타입 오류 방지)
        if worksheet_name == 'subjects':
            for col in ['NFC(탐구욕)', 'NCC(종결욕)']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        elif worksheet_name == 'activities':
            for col in ['nAch(성취)', 'nPow(권력)', 'nAff(친화)', '몰입도(Flow)']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        elif worksheet_name == 'books':
            if '통합적복잡성' in df.columns:
                df['통합적복잡성'] = pd.to_numeric(df['통합적복잡성'], errors='coerce').fillna(0)

        # 모든 컬럼이 비어있는 행만 삭제 (하나라도 데이터가 있으면 유지)
        return df[columns].dropna(how='all')
        
    except Exception as e:
        # 에러 발생 시 빈 DataFrame 반환하여 앱 중단 방지
        return pd.DataFrame(columns=columns)

def add_data(worksheet_name, new_row_df, columns):
    """
    새로운 데이터를 구글 시트에 추가합니다.
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        try:
            existing_data = conn.read(worksheet=worksheet_name, ttl=0, spreadsheet=SHEET_URL)
        except TypeError:
            existing_data = conn.read(worksheet=worksheet_name, ttl=0)
        
        updated_data = pd.concat([existing_data, new_row_df], ignore_index=True)
        
        try:
            conn.update(worksheet=worksheet_name, data=updated_data, spreadsheet=SHEET_URL)
        except TypeError:
            conn.update(worksheet=worksheet_name, data=updated_data)
            
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False

# 데이터 로드
with st.spinner('데이터를 불러오는 중...'):
    df_subjects = get_data("subjects", COLS_SUBJECTS)
    df_activities = get_data("activities", COLS_ACTIVITIES)
    df_books = get_data("books", COLS_BOOKS)
    df_questions = get_data("questions", COLS_QUESTIONS)


# -----------------------------------------------------------------------------
# 3. 사이드바 (가중치 & 백업)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("My Data Reflection")
    st.caption("Archive, Describe, Reflect")
    
    menu = st.radio("MENU", [
        "1. 소개", 
        "2. 경험 모으기 (데이터 입력)", 
        "3. 패턴 찾기 (통계/시각화)", 
        "4. 연결 짓기 (유사 경험 찾기/kNN)", 
        "5. 글로 옮기기 (자소서 작성)"
    ])
    
    st.divider()
    
    # [기능 1] 가중치 조절
    st.markdown("### ⚖️ 가중치 설정 (Weight)")
    st.caption("우선순위를 둘 성향을 조절해보세요. (3번 메뉴의 랭킹에 반영됩니다)")
    
    with st.expander("가중치 상세 조절하기", expanded=True):
        w_ach = st.slider("🎯 성취(nAch) 중요도", 0.0, 3.0, 1.0, 0.1, help="목표 달성, 경쟁 승리, 난관 극복")
        w_pow = st.slider("👑 권력(nPow) 중요도", 0.0, 3.0, 1.0, 0.1, help="영향력 행사, 주도, 리더십")
        w_aff = st.slider("🤝 친화(nAff) 중요도", 0.0, 3.0, 1.0, 0.1, help="유대감, 협력, 사람과의 관계")
        w_flow = st.slider("🌊 몰입(Flow) 중요도", 0.0, 3.0, 1.0, 0.1, help="시간 가는 줄 모르는 즐거움")

    st.divider()
    
    # [기능 2] 데이터 자동 백업
    st.markdown("### 데이터 백업")
    if st.button("CSV 다운로드"):
        now = datetime.now().strftime("%Y%m%d")
        
        csv_sub = df_subjects.to_csv(index=False).encode('utf-8-sig') if not df_subjects.empty else b""
        csv_act = df_activities.to_csv(index=False).encode('utf-8-sig') if not df_activities.empty else b""
        csv_book = df_books.to_csv(index=False).encode('utf-8-sig') if not df_books.empty else b""
        csv_quest = df_questions.to_csv(index=False).encode('utf-8-sig') if not df_questions.empty else b""
        
        c1, c2 = st.columns(2)
        with c1:
            if csv_sub: st.download_button("교과목", csv_sub, f"subjects_{now}.csv", "text/csv")
            if csv_act: st.download_button("활동", csv_act, f"activities_{now}.csv", "text/csv")
        with c2:
            if csv_book: st.download_button("독서", csv_book, f"books_{now}.csv", "text/csv")
            if csv_quest: st.download_button("자소서", csv_quest, f"questions_{now}.csv", "text/csv")
        
        st.success("다운로드 준비 완료 (버튼 클릭)")

# -----------------------------------------------------------------------------
# 4. 메인 페이지
# -----------------------------------------------------------------------------

# [Page 1] Intro
if menu == "1. 소개":
    st.title("My Data Reflection: 흩어진 경험을 모으고 이어보자.")
    st.subheader("Small Data와 kNN을 활용한 개인 맞춤 기록 및 반성 웹")
    st.divider()
    st.header("소개")
    st.markdown("""
    ### 기획 의도: 데이터를 기반으로 나를 기술(Describe)하고 성찰(Reflect)해보자.
    이 앱은 개인의 교과 활동, 대외 활동, 독서 기록을 데이터화하여
    성향을 분석하고 유사한 경험을 연결해주며, 이를 바탕으로 글쓰기를 돕습니다.
    """)

# [Page 2] Archive
elif menu == "2. 경험 모으기 (데이터 입력)":
    st.title("Archive")
    
    tab1, tab2, tab3 = st.tabs(["① 교과목 (Subjects)", "② 대외활동 (Activities)", "③ 독서 (Books)"])

    # Subjects
    with tab1:
        with st.form("sub_form"):
            c1, c2 = st.columns([1, 1])
            s_name = c1.text_input("과목명")
            s_cat = c2.selectbox("분야", [
                "소비자공통", "가계경제/재무설계", "소비자상담/소비자보호", "소비자인사이트",
                "프로그램 언어(Core)", "컴퓨터 시스템 및 인프라 (System)",
                "데이터 사이언스 (Data)", "비즈니스 경영 (Business)", "기타"
            ])
            s_desc = st.text_area("내용", height=100)
            c3, c4 = st.columns(2)
            nfc = c3.slider("탐구욕 (NFC)", 0, 10, 5)
            ncc = c4.slider("종결욕 (NCC)", 0, 10, 5)
            s_memo = st.text_input("메모")
            
            if st.form_submit_button("저장"):
                if s_name:
                    add_data("subjects", pd.DataFrame([[s_name, s_cat, s_desc, nfc, ncc, s_memo]], columns=COLS_SUBJECTS), COLS_SUBJECTS)
                    st.success("저장 완료!")
                    st.rerun()
                else:
                    st.warning("과목명을 입력해주세요.")
        
        if not df_subjects.empty: st.dataframe(df_subjects, use_container_width=True)

    # Activities
    with tab2:
        with st.form("act_form"):
            a_name = st.text_input("활동명")
            a_type = st.selectbox("유형", ["프로젝트(팀)", "개인 연구/개발", "학회/동아리", "인턴/실무", "아르바이트", "봉사", "자격증", "증서"])
            c1, c2, c3 = st.columns(3)
            nAch = c1.slider("성취 (nAch)", 0, 10, 5)
            nPow = c2.slider("권력 (nPow)", 0, 10, 5)
            nAff = c3.slider("친화 (nAff)", 0, 10, 5)
            flow = st.slider("몰입도 (Flow)", 0, 100, 50)
            a_memo = st.text_input("메모")
            
            if st.form_submit_button("저장"):
                if a_name:
                    add_data("activities", pd.DataFrame([[a_name, a_type, "", nAch, nPow, nAff, flow, a_memo]], columns=COLS_ACTIVITIES), COLS_ACTIVITIES)
                    st.success("저장 완료!")
                    st.rerun()
                else:
                    st.warning("활동명을 입력해주세요.")
                    
        if not df_activities.empty: st.dataframe(df_activities, use_container_width=True)

    # Books
    with tab3:
        with st.form("book_form"):
            b_name = st.text_input("책 제목")
            comp = st.slider("통합적 복잡성", 0, 10, 5)
            meaning = st.text_input("의미 부여")
            
            if st.form_submit_button("저장"):
                if b_name:
                    add_data("books", pd.DataFrame([[b_name, comp, meaning]], columns=COLS_BOOKS), COLS_BOOKS)
                    st.success("저장 완료!")
                    st.rerun()
                else:
                    st.warning("책 제목을 입력해주세요.")
                    
        if not df_books.empty: st.dataframe(df_books, use_container_width=True)

# [Page 3] Visualization (Describe)
elif menu == "3. 패턴 찾기 (통계/시각화)":
    st.title("Experience Description")
    
    # 1. 편향 확인 (Bias Check)
    try:
        st.subheader("1. 경험의 편향 확인")
        col_b1, col_b2 = st.columns(2)
        
        with col_b1:
            if not df_subjects.empty:
                sub_counts = df_subjects['분야'].value_counts().reset_index()
                sub_counts.columns = ['분야', '개수']
                fig_sub = px.bar(sub_counts, x='개수', y='분야', orientation='h', 
                                 title="교과목 분야별 이수 현황", color='분야', text='개수')
                st.plotly_chart(fig_sub, use_container_width=True)
            else:
                st.info("교과목 데이터가 없습니다. (Subjects)")
                
        with col_b2:
            if not df_activities.empty:
                act_counts = df_activities['유형'].value_counts().reset_index()
                act_counts.columns = ['유형', '개수']
                fig_act = px.pie(act_counts, values='개수', names='유형', hole=0.4, 
                                 title="대외활동 유형별 분포")
                st.plotly_chart(fig_act, use_container_width=True)
            else:
                st.info("활동 데이터가 없습니다. (Activities)")
    except Exception as e:
        st.error(f"시각화 섹션 1 오류: {e}")

    st.divider()
    
    # 2. 커스텀 랭킹 (가중치 설정)
    try:
        st.subheader("2. 나만의 경험 가중치 랭킹 🏆")
        st.caption("사이드바의 가중치를 변경하면 순위가 실시간으로 바뀝니다.")
        
        if len(df_activities) >= 1:
            act_df = df_activities.copy()
            
            # 전처리
            cols = ['nAch(성취)', 'nPow(권력)', 'nAff(친화)', '몰입도(Flow)']
            # 데이터 타입 안전 변환
            for c in cols:
                act_df[c] = pd.to_numeric(act_df[c], errors='coerce').fillna(0)
            
            # 정규화
            for col in cols:
                min_val = act_df[col].min()
                max_val = act_df[col].max()
                if pd.isna(min_val) or pd.isna(max_val) or (max_val - min_val == 0):
                    act_df[f'{col}_norm'] = 0.5
                else:
                    act_df[f'{col}_norm'] = (act_df[col] - min_val) / (max_val - min_val)

            # 점수 계산
            act_df['My_Score'] = (
                (act_df['nAch(성취)_norm'] * w_ach) +
                (act_df['nPow(권력)_norm'] * w_pow) +
                (act_df['nAff(친화)_norm'] * w_aff) +
                (act_df['몰입도(Flow)_norm'] * w_flow)
            )

            top_df = act_df.sort_values('My_Score', ascending=True).tail(10)
            
            fig_rank = px.bar(top_df, 
                              x='My_Score', y='경험명', orientation='h',
                              color='My_Score', color_continuous_scale='Viridis',
                              text='My_Score',
                              hover_data=['메모', 'nAch(성취)', 'nPow(권력)', 'nAff(친화)', '몰입도(Flow)'])
            
            fig_rank.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig_rank.update_layout(xaxis_visible=False, showlegend=False)
            st.plotly_chart(fig_rank, use_container_width=True)
            
        else:
            st.info("랭킹을 분석할 활동 데이터가 없습니다. '경험 모으기' 탭에서 데이터를 입력해주세요.")
    except Exception as e:
        st.error(f"랭킹 분석 중 오류 발생: {e}")

    st.divider()

    # 3. 키워드 시각화
    try:
        st.subheader("3. 메모 키워드 (Word Cloud)")
        
        # 메모 데이터 수집
        texts = []
        if not df_activities.empty: texts.extend(df_activities['메모'].dropna().astype(str).tolist())
        if not df_subjects.empty: texts.extend(df_subjects['메모'].dropna().astype(str).tolist())
        if not df_books.empty: texts.extend(df_books['의미부여'].dropna().astype(str).tolist())
        
        all_text = " ".join(texts)
        
        if all_text.strip():
            words = re.findall(r'\w+', all_text)
            stop_words = ['하는', '있는', '가장', '통해', '대한', '것이', '내가', '나의', '함', '음', '는', '은', '이', '가', '을', '를', 'nan', 'None']
            words = [w for w in words if len(w) > 1 and w not in stop_words]
            word_counts = Counter(words).most_common(30)
            
            if word_counts:
                wc_df = pd.DataFrame(word_counts, columns=['Keyword', 'Count'])
                fig_tree = px.treemap(wc_df, path=['Keyword'], values='Count',
                                      color='Count', color_continuous_scale='Teal',
                                      title="자주 등장한 키워드 (Treemap)")
                st.plotly_chart(fig_tree, use_container_width=True)
            else:
                st.info("유효한 키워드가 추출되지 않았습니다.")
        else:
            st.info("분석할 메모 데이터가 없습니다. 각 활동 입력 시 '메모'를 남겨주세요.")
    except Exception as e:
        st.error(f"키워드 분석 중 오류 발생: {e}")

# [Page 4] AI Analysis (Reflect)
elif menu == "4. 연결 짓기 (유사 경험 찾기/kNN)":
    st.title("Reference Finding (kNN)")
    
    if len(df_activities) >= 3:
        try:
            act_df = df_activities.copy()
            numeric_cols = ['nAch(성취)', 'nPow(권력)', 'nAff(친화)']
            for c in numeric_cols:
                act_df[c] = pd.to_numeric(act_df[c], errors='coerce').fillna(0)
            
            # PCA
            pca = PCA(n_components=2)
            components = pca.fit_transform(act_df[numeric_cols])
            act_df['x'] = components[:, 0]
            act_df['y'] = components[:, 1]
            act_df['Flow'] = pd.to_numeric(act_df['몰입도(Flow)'], errors='coerce').fillna(0)

            selected_act_name = st.selectbox("기준 경험 선택:", act_df['경험명'].tolist())
            target_row = act_df[act_df['경험명'] == selected_act_name].iloc[0]
            target_vec = target_row[numeric_cols].values.reshape(1, -1)
            
            # kNN
            n_neighbors = min(4, len(act_df))
            knn = NearestNeighbors(n_neighbors=n_neighbors, metric='euclidean')
            knn.fit(act_df[numeric_cols])
            distances, indices = knn.kneighbors(target_vec)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = go.Figure()
                # 전체 점
                fig.add_trace(go.Scatter(
                    x=act_df['x'], y=act_df['y'], mode='markers+text',
                    marker=dict(size=act_df['Flow']*0.3 + 10, color=act_df['Flow'], colorscale='Bluered', showscale=True),
                    text=act_df['경험명'], textposition="top center", name='All',
                    hovertext=act_df['메모']
                ))
                # 선택된 점 (별표)
                fig.add_trace(go.Scatter(
                    x=[target_row['x']], y=[target_row['y']], mode='markers',
                    marker=dict(size=25, color='gold', symbol='star'), name='Selected'
                ))
                
                # 이웃 연결선
                neighbor_indices = indices[0][1:] # 0번은 자기 자신이므로 제외
                for idx in neighbor_indices:
                    neighbor = act_df.iloc[idx]
                    fig.add_trace(go.Scatter(
                        x=[target_row['x'], neighbor['x']], y=[target_row['y'], neighbor['y']],
                        mode='lines', line=dict(color='gray', width=1, dash='dot'), showlegend=False
                    ))
                
                fig.update_layout(title="경험 연결 지도 (Experience Constellation)", height=500, plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.success(f"**{selected_act_name}**와(과) 가장 유사한 경험")
                for i, idx in enumerate(neighbor_indices):
                    neighbor = act_df.iloc[idx]
                    st.markdown(f"**{i+1}. {neighbor['경험명']}**")
                    st.caption(f"메모: {neighbor['메모']}")
                    st.markdown("---")
        except Exception as e:
            st.error(f"분석 중 오류가 발생했습니다: {e}")
            st.info("데이터의 수치값이 올바른지 확인해주세요.")
    else:
        st.warning("분석을 위해 최소 3개 이상의 활동 데이터가 필요합니다.")

# [Page 5] Drafting
elif menu == "5. 글로 옮기기 (자소서 작성)":
    st.title("Data-Driven Drafting")
    
    # 자소서 문항 데이터 확인 (없으면 기본값 생성 제안)
    if df_questions.empty:
        st.info("등록된 자소서 문항이 없습니다. 아래에서 데이터를 추가하거나 시트를 확인해주세요.")
    
    # 신규 문항 추가 기능 (간단 버전)
    with st.expander("📝 새 문항 추가하기"):
        with st.form("new_q_form"):
            new_q_cat = st.text_input("문항 구분 (예: 지원동기, 입사후포부)")
            new_q_content = st.text_area("문항 내용")
            if st.form_submit_button("문항 추가"):
                if new_q_cat and new_q_content:
                    add_data("questions", pd.DataFrame([[new_q_cat, "", new_q_content]], columns=COLS_QUESTIONS), COLS_QUESTIONS)
                    st.success("문항이 추가되었습니다.")
                    st.rerun()
                else:
                    st.warning("구분과 내용을 모두 입력해주세요.")

    if not df_questions.empty:
        # 문항 선택
        q_options = df_questions['문항'].unique()
        selected_q_cat = st.selectbox("질문 선택", q_options)
        
        # 선택된 문항의 내용 표시
        target_q_row = df_questions[df_questions['문항'] == selected_q_cat].iloc[0]
        st.info(f"**Q. {selected_q_cat}**\n\n{target_q_row['내용']}")
        
        # 소재 선택 (Multiselect)
        all_materials = []
        if not df_activities.empty:
            all_materials += [f"[활동] {row['경험명']}" for i, row in df_activities.iterrows()]
        if not df_subjects.empty:
            all_materials += [f"[과목] {row['경험명']}" for i, row in df_subjects.iterrows()]
        if not df_books.empty:
            all_materials += [f"[독서] {row['경험명']}" for i, row in df_books.iterrows()]
            
        selected_materials = st.multiselect("글감 소재 선택 (다중 선택 가능)", all_materials)
        
        # 선택된 소재 상세 정보 텍스트 생성
        evidence_text = ""
        if selected_materials:
            st.markdown("##### 📌 선택된 소재 상세 정보 (참고용)")
            for item in selected_materials:
                try:
                    # 대괄호 안의 타입과 이름 분리 "[활동] 이름"
                    m_type_raw = item.split('] ')[0]
                    m_name = item.split('] ')[1]
                    m_type = m_type_raw.replace('[', '').replace(']', '')
                    
                    detail = ""
                    if m_type == '활동':
                        row = df_activities[df_activities['경험명'] == m_name].iloc[0]
                        detail = f"성취: {row['nAch(성취)']} | 몰입: {row['몰입도(Flow)']} | 메모: {row['메모']}"
                    elif m_type == '과목':
                        row = df_subjects[df_subjects['경험명'] == m_name].iloc[0]
                        detail = f"탐구: {row['NFC(탐구욕)']} | 종결: {row['NCC(종결욕)']} | 메모: {row['메모']}"
                    elif m_type == '독서':
                        row = df_books[df_books['경험명'] == m_name].iloc[0]
                        detail = f"의미부여: {row['의미부여']}"
                    
                    st.caption(f"**{item}**: {detail}")
                    evidence_text += f"- {item}: {detail}\n"
                except IndexError:
                    continue
                except Exception:
                    continue

        # 작성 폼
        with st.form("draft_form"):
            # 기존 작성 내용이 있으면 불러오기 (구현 복잡도를 줄이기 위해 여기선 새 작성만 수행)
            content = st.text_area("작성 공간", height=400, 
                                 value=evidence_text if evidence_text else "",
                                 placeholder="선택한 소재를 바탕으로 글을 작성하세요.")
            
            if st.form_submit_button("저장 (DB 업데이트)"):
                if content:
                    material_str = ", ".join(selected_materials) if selected_materials else "직접 작성"
                    save_cat_name = f"{selected_q_cat} (답변)"
                    add_data("questions", pd.DataFrame([[save_cat_name, material_str, content]], columns=COLS_QUESTIONS), COLS_QUESTIONS)
                    st.success("저장되었습니다!")
                    st.rerun()

# Footer
st.markdown("---")
st.caption("My Data Reflection | Powered by Streamlit & Google Sheets")