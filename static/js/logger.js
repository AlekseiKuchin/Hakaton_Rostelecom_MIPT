console.log("test");

var previousPage = null; // variable to store the previous page
var previousButton = null; // variable to store the previous button


// For import page (called by event on button)
async function apacheLogUpload(file, elemProgress, elemMessage) {
    elemProgress.style.display = 'block';
    const req = new XMLHttpRequest();
    req.upload.addEventListener("progress", function (evt) {
        var percentage = (evt.loaded / evt.total * 100);
        elemProgress.setAttribute('value', percentage);
    });
    req.upload.addEventListener('load', function () {
        elemProgress.style.display = 'none';
        elemMessage.style.display = 'block';
    });
    req.open('POST', '/api/import/apache_log');
    req.setRequestHeader('Content-Type', 'application/octet-stream');
    req.send(file);
}

// On page show
function pageActionStart() {
    const targetPageId = previousButton.getAttribute("href").substring(1);
    switch (targetPageId) {
        case "graph1":
            var graph = document.getElementById('graph1_chart');
            var progress = document.getElementById('graph1_progress');
            fetch('/api/graph_show/graph1').then(async response => {
                const data = await response.json();
                Plotly.newPlot(graph, data, {});
                progress.style.display = 'none';
                graph.style.display = 'block';
            }).catch(error => {
                console.error('Error fetching data:', error);
            });
            break;
        case "import":
            var progress = document.querySelector('#import_form progress');
            var message = document.querySelector('#import_form h3');
            progress.style.display = 'none';
            message.style.display = 'none';
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
    {
        const button = document.querySelector('#import_form input[type=submit]');
        button.addEventListener("click", function (event) {
            event.preventDefault()
            const elemFile = document.querySelector('#import_form input[type=file]');
            const elemProgress= document.querySelector('#import_form progress');
            const elemMessage = document.querySelector('#import_form h3');
            apacheLogUpload(elemFile.files[0], elemProgress, elemMessage);
        });
    }
    var progress = document.getElementById('graph1_progress');
})
