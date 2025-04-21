console.log("test");

var previousPage = null; // variable to store the previous page
var previousButton = null; // variable to store the previous button

// See https://stackoverflow.com/a/64874674
function downloadUrl(url) {
    window.open(url, '_self');
}

// See https://stackoverflow.com/a/39914235
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// For import page (called by event on button)
async function apacheLogUpload(file, elemProgress, elemMessage) {
    elemProgress.style.display = 'block';
    elemMessage.style.display = 'none';
    const req = new XMLHttpRequest();
    req.upload.addEventListener("progress", function (evt) {
        var percentage = (evt.loaded / evt.total * 100);
        elemProgress.setAttribute('value', percentage);
    });
    req.upload.addEventListener('load', async function (evt) {
        elemProgress.style.display = 'none';
        elemMessage.style.display = 'block';
        elemProgress.setAttribute('value', 0);
        elemMessage.textContent = "File uploaded. Waiting DB update..."
    });
    req.addEventListener('readystatechange', async function (evt) {
        // In local files, status is 0 upon success in Mozilla Firefox
        if (req.readyState === XMLHttpRequest.DONE) {
            const status = req.status;
            if (status === 0 || (status >= 200 && status < 400)) {
                elemMessage.textContent = "Import complete."
                getDBstatus("import");
            } else {
                elemMessage.textContent = "FAILED TO UPLOAD!"
            }
        }
    });
    req.open('POST', '/api/import/apache_log');
    req.setRequestHeader('Content-Type', 'application/octet-stream');
    req.send(file);
}

function getDBstatus(page_id) {
    const elem_count = document.querySelector('#' + page_id + ' article p:nth-of-type(1) b');
    const elem_size = document.querySelector('#' + page_id + ' article p:nth-of-type(2) b');
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

// On page show
function pageActionStart() {
    const targetPageId = previousButton.getAttribute("href").substring(1);
    switch (targetPageId) {
        case "graph1":
            var graph = document.getElementById('graph1_chart');
            var progress = document.getElementById('graph1_progress');
            fetch('/api/graph_show/graph1').then(async response => {
                const got_data = await response.json();
                graph.style.display = 'block';
                var layout = got_data.layout;
                layout['autosize'] = true;
                layout['useResizeHandler'] = true;
                layout['width'] = "100%";
                Plotly.newPlot(graph, got_data.data, layout, { responsive: true });
                Plotly.Plots.resize(graph);
                progress.style.display = 'none';
            }).catch(error => {
                console.error('Error fetching data:', error);
            });
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

// On page hide
function pageActionEnd() {
    const targetPageId = previousButton.getAttribute("href").substring(1);
    switch (targetPageId) {
        case "graph1":
            var graph = document.getElementById('graph1_chart');
            var progress = document.getElementById('graph1_progress');
            progress.style.display = 'block';
            graph.style.display = 'none';
            Plotly.purge(graph);
            break;
        case "import":
            break;
        case "export_csv":
            break;
        case "export_parquet":
            break;
        default:
            alert("Unknown page " + targetPageId);
    }
}

function show_page(button, element) {
    if (previousButton) {
        previousPage.style.display = 'none';
        previousButton.removeAttribute('aria-current');
        pageActionEnd();
    }
    // then show the requested page
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
    // Add button events
    const buttons = document.querySelectorAll("a[href]");
    buttons.forEach(button => {
        button.addEventListener("click", function () {
            const targetPage = document.getElementById(this.getAttribute("href").substring(1));
            show_page(button, targetPage);
        });
    });
    // Import apache2 log page
    {
        const button = document.querySelector('#import_form input[type=submit]');
        button.addEventListener("click", function (event) {
            event.preventDefault()
            const elemFile = document.querySelector('#import_form input[type=file]');
            const elemProgress = document.querySelector('#import_form progress');
            const elemMessage = document.querySelector('#import_form h3');
            apacheLogUpload(elemFile.files[0], elemProgress, elemMessage);
        });
    }
    // Export to CSV page
    {
        const button = document.querySelector('#export_csv_form input[type=submit]');
        button.addEventListener("click", function (event) {
            event.preventDefault()
            const elem = document.querySelector('#export_csv_form input[type=number]');
            var number = elem.value ? elem.value : 0;
            downloadUrl("/api/export/csv/" + number)
        });
    }
    // Export to parquet page
    {
        const button = document.querySelector('#export_parquet_form input[type=submit]');
        button.addEventListener("click", function (event) {
            event.preventDefault()
            const elem = document.querySelector('#export_parquet_form input[type=number]');
            var number = elem.value ? elem.value : 0;
            downloadUrl("/api/export/parquet/" + number)
        });
    }
  // Init
  themeSwitcher.init();
})
