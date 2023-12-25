const dataset = document.currentScript.dataset;

async function screenshot(element_id) {
    return html2canvas(
        document.getElementById(element_id), {
            useCORS: true,
            ignoreElements: el => {
                // The following hides unwanted controls, copyrights, pins etc. on the maps and streetview canvases
                return el.classList.contains("gmnoprint") || el.classList.contains("gm-style-cc") 
                || el.id === 'gmimap1' || el.tagName === 'BUTTON' || el.classList.contains("gm-iv-address")
                || el.id === 'time-travel-container'
                || el.getAttribute('src') === 'https://maps.gstatic.com/mapfiles/api-3/images/spotlight-poi3_hdpi.png'
                || el.getAttribute('src') === 'https://maps.gstatic.com/mapfiles/api-3/images/spotlight-poi3.png'
                || el.getAttribute('aria-label') === 'Open this area in Google Maps (opens a new window)';
            },
        }
    ).then(canvas => {
        // Convert the image to a dataURL to send to backend
        // Can also convert to image/png but heavier
        return canvas.toDataURL('image/jpeg');
    })
}

/*
* Screenshot only the streetview. Called when the screenshot button is clicked.
*/
async function screenshotStreetview(e) {
    e.preventDefault();

    const caseId = document.getElementById('case-id').innerText;
    
    const postData = {
        id: caseId,
        pano: window.sv.getPano(),
        date: document.getElementById('current-date').innerText, 
        img: await screenshot('streetview'),
    }
    fetch("/upload", {
        method: "POST",
        mode: "same-origin", 
        cache: "no-cache", 
        credentials: "same-origin", 
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(postData),
    }).then(() => alert('OK'))
}

document.addEventListener("DOMContentLoaded", () => { 
    const screenshotButton = document.getElementById('btn-screenshot');
    screenshotButton.addEventListener('click', (e) => {
        screenshotStreetview(e);
    });
});

