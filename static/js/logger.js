console.log("test");

var previousPage = null; // variable to store the previous page
var previousButton = null; // variable to store the previous button

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
    const buttons = document.querySelectorAll("a[href]");
    buttons.forEach(button => {
        button.addEventListener("click", function () {
            const targetPage = document.getElementById(this.getAttribute("href").substring(1));
            show_page(button, targetPage);
        });
    });
})
