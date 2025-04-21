console.log("test");

var previousPage = null;
var previousButton = null;

function saveDateRange(id, start, end) {
    localStorage.setItem(`date_${id}_start`, start);
    localStorage.setItem(`date_${id}_end`, end);
}
function loadDateRange(id) {
    return {
        start: localStorage.getItem(`date_${id}_start`),
        end: localStorage.getItem(`date_${id}_end`)
    };
}

function downloadUrl(url) {
    window.open(url, '_self');
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function apacheLogUpload(file, elemProgress, elemMessage) {
    elemProgress.style.display = 'block';
    elemMessage.style.display = 'block';
    var started_at = new Date();
    const req = new XMLHttpRequest();
    req.upload.addEventListener("progress", function (evt) {
        var seconds_elapsed = (new Date().getTime() - started_at.getTime()) / 1000;
        var percentage = (evt.loaded / evt.total * 100);
        var bytes_per_second = seconds_elapsed ? evt.loaded / seconds_elapsed : 0;
        var remaining_bytes = evt.total - evt.loaded;
        var seconds_remaining = seconds_elapsed ? Math.round(remaining_bytes / bytes_per_second) : 'calculating';
        elemMessage.textContent = "Time left: " + seconds_remaining + " seconds.";
        elemProgress.setAttribute('value', percentage);
    });
    req.upload.addEventListener('load', async function (evt) {
        elemProgress.style.display = 'none';
        elemProgress.setAttribute('value', 0);
        elemMessage.textContent = "File uploaded. Waiting DB update...";
    });
    req.addEventListener('readystatechange', async function (evt) {
        if (req.readyState === XMLHttpRequest.DONE) {
            const status = req.status;
            if (status === 0 || (status >= 200 && status < 400)) {
                elemMessage.textContent = "Import complete.";
                getDBstatus("import");
            } else {
                elemMessage.textContent = "FAILED TO UPLOAD!";
            }
        }
    });
    req.open('POST', '/api/import/apache_log');
    req.setRequestHeader('Content-Type', 'application/octet-stream');
    req.send(file);
}

function getDBstatus(targetPageId) {
    const elem_count = document.querySelector('#' + targetPageId + ' article p:nth-of-type(1) b');
    const elem_size = document.querySelector('#' + targetPageId + ' article p:nth-of-type(2) b');
    elem_count.setAttribute('aria-busy', true);
    elem_size.setAttribute('aria-busy', true);
    fetch('/api/db/db_size').then(async response => {
        const got_data = await response.json();
        elem_count.textContent = got_data['count'];
        elem_size.textContent = got_data['size_human'];
        elem_count.setAttribute('aria-busy', false);
        elem_size.setAttribute('aria-busy', false);
    }).catch(error => {
        console.error('Error fetching data:', error);
    });
}

function getDBDateRange(targetPageId) {
    var time_start = document.querySelector('#' + targetPageId + ' form input[name=date_start]');
    var time_end = document.querySelector('#' + targetPageId + ' form input[name=date_end]');
    // Попытаться восстановить ранее сохранённые даты
    var stored = loadDateRange(targetPageId);
    if (stored.start) time_start.valueAsNumber = parseInt(stored.start);
    if (stored.end)   time_end.valueAsNumber   = parseInt(stored.end);

    time_start.setAttribute('aria-busy', true);
    time_end.setAttribute('aria-busy', true);
    fetch('/api/db/get_date_range').then(async response => {
        const got_data = await response.json();
        time_start.valueAsNumber = got_data['min_time'] * 1000;
        time_end.valueAsNumber = got_data['max_time'] * 1000;
        time_start.setAttribute('aria-busy', false);
        time_end.setAttribute('aria-busy', false);
        drawGraph(targetPageId, {}); // Перерисовываем график после установки дат
    }).catch(error => {
        console.error('Error fetching date range:', error);
    });
}

function drawGraph(targetPageId, params) {
    var graph = document.querySelector('#' + targetPageId + ' div.chart');
    var progress = document.querySelector('#' + targetPageId + ' progress');
    var url = '/api/graph_show/' + targetPageId;
    if (['graph1', 'graph2', 'graph3'].includes(targetPageId)) {
        var time_start = document.querySelector('#' + targetPageId + ' form input[name=date_start]');
        var time_end = document.querySelector('#' + targetPageId + ' form input[name=date_end]');
        var start_time = time_start.valueAsNumber ? Math.floor(time_start.valueAsNumber / 1000) : 0;
        var end_time = time_end.valueAsNumber ? Math.floor(time_end.valueAsNumber / 1000) : 0;
        url += `?start_time=${start_time}&end_time=${end_time}`;
    }
    fetch(url).then(async response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const got_data = await response.json();
        graph.style.display = 'block';
        var layout = got_data.layout;
        layout['autosize'] = true;
        layout['useResizeHandler'] = true;
        layout['width'] = "100%";
        Plotly.newPlot(graph, got_data.data, layout, { responsive: true });
        Plotly.Plots.resize(graph);
        progress.style.display = 'none';

        if (targetPageId === 'graph3') {
            graph.on('plotly_click', function(data) {
                if (data.points.length > 0) {
                    var ip = data.points[0].x;
                    fetch(`/api/details/ip/${ip}`)
                        .then(response => {
                            if (!response.ok) {
                                throw new Error(`HTTP error! status: ${response.status}`);
                            }
                            return response.json();
                        })
                        .then(details => {
                            var tableDiv = document.getElementById('ip-details-table');
                            tableDiv.innerHTML = '';
                            var table = document.createElement('table');
                            table.innerHTML = `
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Method</th>
                                    <th>Path</th>
                                    <th>Status</th>
                                    <th>Bytes Sent</th>
                                    <th>Response Time</th>
                                </tr>
                            `;
                            details.forEach(row => {
                                table.innerHTML += `
                                    <tr>
                                        <td>${row.timestamp}</td>
                                        <td>${row.method}</td>
                                        <td>${row.path}</td>
                                        <td>${row.status}</td>
                                        <td>${row.bytes_sent}</td>
                                        <td>${row.response_time}</td>
                                    </tr>
                                `;
                            });
                            tableDiv.appendChild(table);
                        })
                        .catch(error => console.error('Ошибка загрузки деталей:', error));
                }
            });
        }
    }).catch(error => {
        console.error('Error fetching graph data:', error);
        progress.style.display = 'none';
        graph.innerHTML = '<p>Ошибка загрузки данных. Попробуйте позже.</p>';
    });
}

function destroyGraph(targetPageId, params) {
    var graph = document.querySelector('#' + targetPageId + ' div.chart');
    var progress = document.querySelector('#' + targetPageId + ' progress');
    progress.style.display = 'block';
    graph.style.display = 'none';
    Plotly.purge(graph);
    if (targetPageId === 'graph3') {
        var tableDiv = document.getElementById('ip-details-table');
        if (tableDiv) {
            tableDiv.innerHTML = '';
        }
    }
}

function pageActionStart() {
    const targetPageId = previousButton.getAttribute("href").substring(1);
    switch (targetPageId) {
        case "graph1":
        case "graph2":
        case "graph3":
            getDBDateRange(targetPageId); // Инициализируем даты и рисуем график
            break;
        case "graph4":
        case "graph5":
            drawGraph(targetPageId, {});
            break;
        case "import":
            getDBstatus(targetPageId);
            var progress = document.querySelector('#import_form progress');
            var message = document.querySelector('#import_form h3');
            progress.style.display = 'none';
            message.style.display = 'none';
            break;
        case "export_csv":
            getDBstatus(targetPageId);
            break;
        case "export_parquet":
            getDBstatus(targetPageId);
            break;
        default:
            alert("Unknown page " + targetPageId);
    }
}

function pageActionEnd() {
    const targetPageId = previousButton.getAttribute("href").substring(1);
    switch (targetPageId) {
        case "graph1":
        case "graph2":
        case "graph3":
        case "graph4":
        case "graph5":
            destroyGraph(targetPageId, {});
            break;
        default:
            break;
    }
}

function show_page(button, element) {
    if (previousButton) {
        previousPage.style.display = 'none';
        previousButton.removeAttribute('aria-current');
        pageActionEnd();
    }
    previousPage = element;
    previousButton = button;
    button.setAttribute("aria-current", "page");
    element.style.display = 'block';
    pageActionStart();
}

document.addEventListener("DOMContentLoaded", function () {
    const currentUrl = window.location.href;
    {
        const currentPageId = currentUrl.split("#")[1];
        const currentButton = document.querySelector(`a[href="#${currentPageId}"]`);
        if (currentButton) {
            const CurrentPage = document.getElementById(currentButton.getAttribute("href").substring(1));
            show_page(currentButton, CurrentPage);
        }
    }
    const buttons = document.querySelectorAll("a[href]");
    buttons.forEach(button => {
        button.addEventListener("click", function () {
            const targetPage = document.getElementById(this.getAttribute("href").substring(1));
            show_page(button, targetPage);
        });
    });
    {
        const button = document.querySelector('#import_form input[type=submit]');
        button.addEventListener("click", function (event) {
            event.preventDefault();
            const elemFile = document.querySelector('#import_form input[type=file]');
            const elemProgress = document.querySelector('#import_form progress');
            const elemMessage = document.querySelector('#import_form h3');
            apacheLogUpload(elemFile.files[0], elemProgress, elemMessage);
        });
    }
    {
        const button = document.querySelector('#export_csv_form input[type=submit]');
        button.addEventListener("click", function (event) {
            event.preventDefault();
            const elem = document.querySelector('#export_csv_form input[type=number]');
            var number = elem.value ? elem.value : 0;
            downloadUrl("/api/export/csv/" + number);
        });
    }
    {
        const button = document.querySelector('#export_parquet_form input[type=submit]');
        button.addEventListener("click", function (event) {
            event.preventDefault();
            const elem = document.querySelector('#export_parquet_form input[type=number]');
            var number = elem.value ? elem.value : 0;
            downloadUrl("/api/export/parquet/" + number);
        });
    }
    ["graph1", "graph2", "graph3"].forEach(pageId => {
    const timeStartInput = document.querySelector('#' + pageId + ' form input[name=date_start]');
    const timeEndInput = document.querySelector('#' + pageId + ' form input[name=date_end]');

    timeStartInput.addEventListener("change", function () {
        // Сохраняем выбранные даты в localStorage
        saveDateRange(
            pageId,
            timeStartInput.valueAsNumber,
            timeEndInput.valueAsNumber
        );
        destroyGraph(pageId, {});
        drawGraph(pageId, {});
    });

    timeEndInput.addEventListener("change", function () {
        saveDateRange(
            pageId,
            timeStartInput.valueAsNumber,
            timeEndInput.valueAsNumber
        );
        destroyGraph(pageId, {});
        drawGraph(pageId, {});
    });
});

    themeSwitcher.init();
});
