import dash 
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import clickhouse_connect
import warnings
import io
import base64
from datetime import datetime

# Подавляем предупреждения
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Подключение к ClickHouse
client = clickhouse_connect.get_client(
    host='77.95.201.152',
    port=18123,
    database='default',
    user='default',
    password='1234'
)

# Функция для получения минимальной и максимальной даты из таблицы logs
def get_date_range():
    query = """
    SELECT MIN(timestamp), MAX(timestamp)
    FROM logs
    """
    result = client.query_df(query)
    if result.empty:
        return '2023-01-01', '2023-12-31'
    # Явно форматируем даты
    min_date = pd.to_datetime(result.iloc[0, 0]).strftime('%Y-%m-%d')
    max_date = pd.to_datetime(result.iloc[0, 1]).strftime('%Y-%m-%d')
    return min_date, max_date

min_date, max_date = get_date_range()

# Функции для получения данных
def get_daily_requests(start_date=None, end_date=None):
    query = """
    SELECT toDate(timestamp) as date, COUNT(*) as total_requests
    FROM logs
    WHERE 1=1
    """
    if start_date and end_date:
        # Явно преобразуем даты в формат YYYY-MM-DD
        start_date = pd.to_datetime(start_date).strftime('%Y-%m-%d')
        end_date = pd.to_datetime(end_date).strftime('%Y-%m-%d')
        query += f" AND timestamp BETWEEN toDate('{start_date}') AND toDate('{end_date}')"
    query += """
    GROUP BY date
    ORDER BY date
    """
    return client.query_df(query)

def get_daily_failures(start_date=None, end_date=None):
    query = """
    SELECT toDate(timestamp) as date, COUNT(*) as total_failures
    FROM logs
    WHERE status >= 400
    """
    if start_date and end_date:
        # Явно преобразуем даты в формат YYYY-MM-DD
        start_date = pd.to_datetime(start_date).strftime('%Y-%m-%d')
        end_date = pd.to_datetime(end_date).strftime('%Y-%m-%d')
        query += f" AND timestamp BETWEEN toDate('{start_date}') AND toDate('{end_date}')"
    query += """
    GROUP BY date
    ORDER BY date
    """
    return client.query_df(query)

def get_top_ips(start_date=None, end_date=None):
    query = """
    SELECT ip, COUNT(*) as request_count
    FROM logs
    WHERE 1=1
    """
    if start_date and end_date:
        # Явно преобразуем даты в формат YYYY-MM-DD
        start_date = pd.to_datetime(start_date).strftime('%Y-%m-%d')
        end_date = pd.to_datetime(end_date).strftime('%Y-%m-%d')
        query += f" AND timestamp BETWEEN toDate('{start_date}') AND toDate('{end_date}')"
    query += """
    GROUP BY ip
    ORDER BY request_count DESC
    LIMIT 10
    """
    return client.query_df(query)

# Определение базовых стилей и тем
external_stylesheets = [
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap'
]

# Цветовые схемы для тем
themes = {
    'light': {
        'container_bg': 'linear-gradient(to bottom, #e6f0fa, #ffffff)',
        'text': '#34495e',
        'primary_line': '#1976d2',
        'failure_line': '#f44336',
        'card_bg': '#ffffff',
        'button_bg': '#1976d2',
        'button_hover': '#155a8a',
        'download_bg': '#388e3c',
        'download_hover': '#2e7d32',
        'graph_grid': 'rgba(200,200,200,0.2)',
        'page_bg': '#ffffff',
    },
    'dark': {
        'container_bg': 'linear-gradient(to bottom, #2c3e50, #34495e)',
        'text': '#ecf0f1',
        'primary_line': '#4fc3f7',
        'failure_line': '#ef5350',
        'card_bg': '#3b4a59',
        'button_bg': '#4fc3f7',
        'button_hover': '#3aa1d5',
        'download_bg': '#66bb6a',
        'download_hover': '#57a05a',
        'graph_grid': 'rgba(150,150,150,0.3)',
        'page_bg': '#2c3e50',
    }
}

# Фиксированные стили, не зависящие от темы
base_styles = {
    'header': {
        'textAlign': 'center',
        'fontSize': '2.5em',
        'fontWeight': '700',
        'marginBottom': '40px',
    },
    'graph_card': {
        'borderRadius': '10px',
        'boxShadow': '0 4px 8px rgba(0, 0, 0, 0.1)',
        'padding': '15px',
        'marginBottom': '20px',
        'transition': 'transform 0.2s, box-shadow 0.2s',
        'minHeight': '400px',
        'boxSizing': 'border-box',
        'width': '100%',
    },
    'graph_title': {
        'fontSize': '1.5em',
        'fontWeight': '500',
        'marginBottom': '10px',
    },
    'button_container': {
        'display': 'flex',
        'justifyContent': 'space-between',
        'alignItems': 'center',
        'marginBottom': '20px',
    },
    'footer': {
        'textAlign': 'center',
        'marginTop': '40px',
        'fontSize': '0.9em',
    },
    'grid': {
        'display': 'grid',
        'gridTemplateColumns': 'repeat(2, 1fr)',
        'gap': '10px',
        'marginBottom': '20px',
        'maxWidth': '100%',
        'boxSizing': 'border-box',
    },
    'full_width': {
        'gridColumn': '1 / -1',
    },
    'date_picker': {
        'marginBottom': '20px',
        'textAlign': 'center',
    },
    'theme_selector': {
        'marginBottom': '20px',
        'textAlign': 'center',
        'fontSize': '1em',
    }
}

# Создание приложения Dash
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

# Макет дашборда с переключателем темы
app.layout = html.Div(id='page-container', children=[
    html.Div([
        html.H1("Дашборд логов Ростелекома", id='header', style=base_styles['header']),
        
        # Переключатель темы
        html.Div([
            dcc.RadioItems(
                id='theme-selector',
                options=[
                    {'label': 'Light', 'value': 'light'},
                    {'label': 'Dark', 'value': 'dark'}
                ],
                value='light',
                inline=True,
                labelStyle={'marginRight': '20px', 'cursor': 'pointer'}
            )
        ], style=base_styles['theme_selector']),
        
        html.Div([
            dcc.DatePickerRange(
                id='date-picker',
                min_date_allowed=min_date,
                max_date_allowed=max_date,
                initial_visible_month=min_date,
                start_date=min_date,
                end_date=max_date,
                display_format='DD.MM.YYYY',
                style={'fontFamily': 'Inter, sans-serif'}
            ),
        ], style=base_styles['date_picker']),
        html.Div([
            html.Button("Обновить данные", id='refresh-button', n_clicks=0),
            html.A("Скачать в CSV", id='download-link-csv', download="logs_data.csv", href=""),
            html.A("Скачать в Parquet", id='download-link-parquet', download="logs_data.parquet", href=""),
        ], style=base_styles['button_container'], id='button-container'),
        html.Div([
            html.Div([
                html.H2("Количество запросов по дням", style=base_styles['graph_title']),
                dcc.Graph(id='requests-graph', config={'doubleClick': 'reset',
                                                      'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
                                                      'displaylogo': False,
                                                      'responsive': True}),
            ], className='graph-card', style=base_styles['graph_card']),
            html.Div([
                html.H2("Количество отказов по дням", style=base_styles['graph_title']),
                dcc.Graph(id='failures-graph', config={'doubleClick': 'reset',
                                                      'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
                                                      'displaylogo': False,
                                                      'responsive': True}),
            ], className='graph-card', style=base_styles['graph_card']),
            html.Div([
                html.H2("Топ-10 IP по количеству запросов", style=base_styles['graph_title']),
                dcc.Graph(id='top-ips-graph', config={'doubleClick': 'reset',
                                                      'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
                                                      'displaylogo': False,
                                                      'responsive': True}),
            ], className='graph-card', style={**base_styles['graph_card'], **base_styles['full_width']}),
        ], style=base_styles['grid']),
        html.Footer("Создано командой крутых чуваков, 2025", id='footer', style=base_styles['footer']),
    ], id='container')
])

# Функция для создания пустого графика с сообщением
def create_empty_graph(message="Нет данных для отображения", font_color='#34495e'):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=20, color=font_color),
    )
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=40, r=40, t=20, b=40),
    )
    return fig

# Обновление графиков и стилей согласно выбранной теме
@app.callback(
    [Output('requests-graph', 'figure'),
     Output('failures-graph', 'figure'),
     Output('top-ips-graph', 'figure'),
     Output('download-link-csv', 'href'),
     Output('download-link-parquet', 'href'),
     Output('container', 'style'),
     Output('refresh-button', 'style'),
     Output('download-link-csv', 'style'),
     Output('download-link-parquet', 'style'),
     Output('header', 'style'),
     Output('footer', 'style')],
    [Input('refresh-button', 'n_clicks'),
     Input('date-picker', 'start_date'),
     Input('date-picker', 'end_date'),
     Input('theme-selector', 'value')]
)
def update_dashboard(n_clicks, start_date, end_date, theme):
    # Определяем цвета по выбранной теме
    theme_colors = themes.get(theme, themes['light'])
    bg_color = theme_colors['container_bg']
    text_color = theme_colors['text']
    primary_line = theme_colors['primary_line']
    failure_line = theme_colors['failure_line']
    card_bg = theme_colors['card_bg']
    graph_grid = theme_colors['graph_grid']
    
    # Обновляем стили контейнера и кнопок
    container_style = {
        'maxWidth': '1200px',
        'margin': '0 auto',
        'padding': '20px',
        'fontFamily': 'Inter, sans-serif',
        'background': bg_color,
        'minHeight': '100vh',
        'color': text_color,
        'overflowX': 'hidden',
        'boxSizing': 'border-box',
    }
    button_style = {
        'backgroundColor': theme_colors['button_bg'],
        'color': 'white',
        'border': 'none',
        'padding': '10px 20px',
        'borderRadius': '5px',
        'cursor': 'pointer',
        'fontSize': '1em',
        'transition': 'background-color 0.3s',
    }
    download_style = {
        'backgroundColor': theme_colors['download_bg'],
        'color': 'white',
        'padding': '10px 20px',
        'borderRadius': '5px',
        'textDecoration': 'none',
        'fontSize': '1em',
        'transition': 'background-color 0.3s',
    }
    
    # Получаем данные
    df_requests = get_daily_requests(start_date, end_date)
    df_failures = get_daily_failures(start_date, end_date)
    df_top_ips = get_top_ips(start_date, end_date)

    # Логирование для отладки
    print("df_requests columns:", df_requests.columns.tolist())
    print("df_requests head:", df_requests.head().to_dict())
    print("df_failures columns:", df_failures.columns.tolist())
    print("df_failures head:", df_failures.head().to_dict())
    print("df_top_ips columns:", df_top_ips.columns.tolist())
    print("df_top_ips head:", df_top_ips.head().to_dict())

    # График запросов
    if df_requests.empty or 'date' not in df_requests.columns or 'total_requests' not in df_requests.columns:
        fig_requests = create_empty_graph("Нет данных о запросах", font_color=text_color)
    else:
        fig_requests = px.line(df_requests, x='date', y='total_requests', title=None, line_shape='linear')
        fig_requests.update_traces(line_color=primary_line, line_width=2)
        fig_requests.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter, sans-serif", size=12, color=text_color),
            xaxis_title="Дата",
            yaxis_title="Запросы",
            showlegend=False,
            margin=dict(l=40, r=40, t=20, b=40),
            xaxis=dict(showgrid=True, gridcolor=graph_grid),
            yaxis=dict(showgrid=True, gridcolor=graph_grid),
            hovermode='x unified',
        )

    # График отказов
    if df_failures.empty or 'date' not in df_failures.columns or 'total_failures' not in df_failures.columns:
        fig_failures = create_empty_graph("Нет данных об отказах", font_color=text_color)
    else:
        fig_failures = px.line(df_failures, x='date', y='total_failures', title=None, line_shape='linear')
        fig_failures.update_traces(line_color=failure_line, line_width=2)
        fig_failures.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter, sans-serif", size=12, color=text_color),
            xaxis_title="Дата",
            yaxis_title="Отказы",
            showlegend=False,
            margin=dict(l=40, r=40, t=20, b=40),
            xaxis=dict(showgrid=True, gridcolor=graph_grid),
            yaxis=dict(showgrid=True, gridcolor=graph_grid),
            hovermode='x unified',
        )

    # График топ-IP
    if df_top_ips.empty or 'ip' not in df_top_ips.columns or 'request_count' not in df_top_ips.columns:
        fig_top_ips = create_empty_graph("Нет данных о топ-10 IP", font_color=text_color)
    else:
        fig_top_ips = px.bar(df_top_ips, x='ip', y='request_count', title=None, text_auto=True)
        fig_top_ips.update_traces(marker_color=primary_line)
        fig_top_ips.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter, sans-serif", size=12, color=text_color),
            xaxis_title="IP",
            yaxis_title="Запросы",
            showlegend=False,
            margin=dict(l=40, r=40, t=20, b=40),
            xaxis=dict(tickangle=45),
        )

    # Экспорт в CSV
    csv_href = ""
    if not df_requests.empty:
        csv_string = df_requests.to_csv(index=False)
        csv_href = f"data:text/csv;charset=utf-8,{csv_string}"

    # Экспорт в Parquet
    parquet_href = ""
    if not df_requests.empty:
        buffer = io.BytesIO()
        df_requests.to_parquet(buffer, index=False)
        parquet_data = buffer.getvalue()
        parquet_href = f"data:application/octet-stream;base64,{base64.b64encode(parquet_data).decode()}"

    # Обновляем стили заголовка и подвала с учетом цвета текста
    header_style = {**base_styles['header'], 'color': text_color}
    footer_style = {**base_styles['footer'], 'color': text_color}

    return (fig_requests, fig_failures, fig_top_ips, csv_href, parquet_href,
            container_style, button_style, download_style, download_style,
            header_style, footer_style)

# Улучшенные hover-эффекты для кнопок через CSS (с эффектами масштабирования и плавного перехода)
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Дашборд логов Ростелекома</title>
        {%favicon%}
        {%css%}
        <style>
            button:hover {
                background-color: inherit !important;
                transform: scale(1.05);
            }
            a[href*="logs_data"]:hover {
                background-color: inherit !important;
                transform: scale(1.05);
            }
            /* Эффект подъёма карточек при наведении */
            .graph-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            }
            /* Ограничиваем ширину карточек и графиков */
            .graph-card {
                max-width: 100% !important;
                box-sizing: border-box;
            }
            .graph-card > div {
                width: 100% !important;
                max-width: 100% !important;
            }
            /* Ограничиваем контейнер */
            #container {
                max-width: 1200px !important;
                overflow-x: hidden !important;
            }
            /* Ограничиваем ширину графиков Plotly */
            .js-plotly-plot, .plotly {
                width: 100% !important;
                max-width: 100% !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)
