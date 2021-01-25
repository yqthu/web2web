const numSteps = 20.0;

let prevRatio = 0.0;
let increasingColor = "rgba(40, 40, 190, ratio)";
let decreasingColor = "rgba(190, 40, 40, ratio)";
let canvasScale = 3;

let canvasRects = {};
let textElements = {};

function $xx(xpath)
{
    let results = [];
    let query = document.evaluate(xpath, document || document,
        null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
    for (let i = 0, length = query.snapshotLength; i < length; ++i) {
        results.push(query.snapshotItem(i));
    }
    return results;
}

// FIXME: MutationObserver?
// window.addEventListener("load", (event) => {
initCanvas();
createObserver();
// }, false);

function initCanvas() {
  let canvasNode = document.createElement("canvas");
  canvasNode.setAttribute('height', Math.floor(window.innerHeight / canvasScale));
  canvasNode.setAttribute('width', Math.floor(window.innerWidth / canvasScale));
  canvasNode.setAttribute('class', 'canvasContainer')
  canvasNode.setAttribute('style', 'z-index: 999;')
  document.body.appendChild(canvasNode);
  return canvasNode;
}

function createObserver() {
  let observer;

  let options = {
    root: null,
    rootMargin: "0px",
    threshold: buildThresholdList()
  };

  observer = new IntersectionObserver(handleIntersect, options);
  ["//*[string-length(text()) > 0]"].forEach((path) =>
    $xx(path).forEach(
        (element, index) => {
          for (const node of element.childNodes) {
            if (node.nodeType == 3 && node.nodeValue.trim().length > 0) {
              element.tracker_id = index;
              observer.observe(element);
              textElements[element.tracker_id] = element;
            }
          }
      }
    )
  )
}

// FIXME: MutationObserver?
window.addEventListener("scroll", (event) => {
  let canvasNode = $xx('//canvas')[0];
  let ctx = canvasNode.getContext("2d");
  ctx.clearRect(0,0,canvasNode.width,canvasNode.height);
  ctx.fillStyle = "red";
  ctx.beginPath();
  for (const [key, el] of Object.entries(textElements)) {
    if (el.__tracker_isVisible) {
      let rect = el.getBoundingClientRect();
      ctx.fillRect(
        Math.floor(rect.x / canvasScale),
        Math.floor(rect.y / canvasScale),
        Math.floor(el.__tracker_intersectWidth / canvasScale),
        Math.floor(el.__tracker_intersectHeight / canvasScale)
      );
    }
  }
  ctx.stroke();
}, false);


function handleIntersect(entries, observer) {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        let te = textElements[entry.target.tracker_id];
        te.__tracker_isVisible = true;
        te.__tracker_intersectWidth = entry.intersectionRect.width;
        te.__tracker_intersectHeight = entry.intersectionRect.height;
        canvasRects[entry.target.tracker_id] = entry.intersectionRect;
      } else {
        textElements[entry.target.tracker_id].__tracker_isVisible = false;
      }
    });
  }

function buildThresholdList() {
    let thresholds = [];
    let numSteps = 100;
  
    for (let i=1.0; i<=numSteps; i++) {
      let ratio = i/numSteps;
      thresholds.push(ratio);
    }
  
    thresholds.push(0);
    return thresholds;
  }