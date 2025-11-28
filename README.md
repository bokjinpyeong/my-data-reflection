My Data Reflection

A web application for personal data tracking and reflection based on small data and kNN analysis. This project archives personal experiences (subjects, activities, books) and visualizes patterns to help with self-reflection and drafting personal statements.

Features

Archive: Record data on school subjects, extracurricular activities, and reading logs.

Describe: Visualize data distribution and generate weighted rankings based on achievement and interest.

Reflect: Find similar experiences using kNN (k-Nearest Neighbors) algorithms to discover connections between different activities.

Draft: Select recorded materials to draft personal statements or essays.

Tech Stack

Python 3.9+

Streamlit

Pandas & NumPy

Plotly

Scikit-learn

Google Sheets API (st-gsheets-connection)

Installation

Clone the repository

Install dependencies:

pip install -r requirements.txt


Run the application:

streamlit run app.py


My Data Reflection (국문)

개인의 경험(Small Data)을 기록하고 kNN 알고리즘을 활용해 경험 간의 연결성을 분석하는 웹 애플리케이션입니다. 교과목, 대외활동, 독서 데이터를 축적하고 이를 시각화하여 자기소개서 작성 및 자아 성찰을 돕습니다.

주요 기능

경험 모으기 (Archive): 교과목, 대외활동, 독서 데이터를 구글 시트에 기록합니다.

패턴 찾기 (Describe): 입력된 데이터의 편향을 확인하고 성취도와 흥미도 가중치를 적용하여 나만의 랭킹을 산출합니다.

연결 짓기 (Reflect): kNN 알고리즘을 이용해 특정 경험과 유사한 성격을 가진 다른 경험을 추천합니다.

글로 옮기기 (Draft): 축적된 소재를 선택하여 자기소개서 초안을 작성하고 저장합니다.

기술 스택

Python 3.9+

Streamlit

Pandas & NumPy

Plotly

Scikit-learn

Google Sheets API