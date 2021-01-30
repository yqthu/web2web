let canvasScale = 3;
let canvasRects = {};
var recordedElements = null;

function $xx(xpath) {
    let results = [];
    let query = document.evaluate(xpath, document || document,
        null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
    for (let i = 0, length = query.snapshotLength; i < length; ++i) {
        results.push(query.snapshotItem(i));
    }
    return results;
}

var defaultElementCollector = (elementList) => (element, index) => {
  element.tracker_id = index;
  elementList[element.tracker_id] = element;
};

function isScrolledIntoView(el) {
  var rect = el.getBoundingClientRect();
  var elemTop = rect.top;
  var elemBottom = rect.bottom;

  isVisible = elemTop < window.innerHeight && elemBottom >= 0;
  return isVisible;
}

class RecordedElements {
  constructor(xpath, elementCollector = defaultElementCollector) {
    this.xpath = xpath;
    this.observer = null;
    this.elements = {};
    this.elementCollector = elementCollector;
  }

  createIntersectionObserver() {
    let options = {
      root: null,
      rootMargin: "0px",
      threshold: buildThresholdList(),
      trackVisibility: true,
      delay: 200
    };
  
    if (this.observer) {
      this.observer.disconnect();
    }
    let els = $xx(this.xpath);
    els.forEach(this.elementCollector(this.elements));
    this.observer = new IntersectionObserver(handleIntersect(this), options);
    els.forEach((element) => {
      // FIXME: The first time 
      let rect = element.getBoundingClientRect();
      element.__tracker_isVisible = isScrolledIntoView(element);
      element.__tracker_intersectWidth = rect.width;
      element.__tracker_intersectHeight = rect.height;
      this.observer.observe(element);
    });
    return this.observer;
  }
}

var mutationCallback = (mutationsList, observer) => {
  // console.log(mutationsList);
  recordedElements = [
    new RecordedElements("//*[string-length(text()) > 0]",
    (elementList) => (element, index) => {
      for (const node of element.childNodes) {
        if (node.nodeType == 3 && node.nodeValue.trim().length > 0) {
          element.tracker_id = index;
          elementList[element.tracker_id] = element;
        }
      }
    }),
    new RecordedElements("//img"),
    new RecordedElements("//button"),
    new RecordedElements("//svg")
  ];
  recordedElements.forEach((recEle) => {
    recEle.createIntersectionObserver();
  });
  let elementLists = [
    [recordedElements[1].elements, 'blue'],
    [recordedElements[0].elements, 'red'],
    [recordedElements[2].elements, 'green'],
    [recordedElements[3].elements, 'white'],
  ];
  scrollCallback(elementLists)(1);
  addScrollListener(elementLists);
};

function createMutationObserver() {
  let config = { attributes: false, childList: true, subtree: true };
  var mo = new MutationObserver(mutationCallback);
  mo.observe(document.body, config);
}

function initCanvas() {
  let canvasNode = document.createElement("canvas");
  canvasNode.setAttribute('height', Math.floor(window.innerHeight / canvasScale));
  canvasNode.setAttribute('width', Math.floor(window.innerWidth / canvasScale));
  canvasNode.setAttribute('class', 'canvasContainer')
  canvasNode.setAttribute('style', 'z-index: 999;')
  document.body.appendChild(canvasNode);
  return canvasNode;
}

function scrollCallback(elementLists) {
  return (_) => {
    let canvasNode = $xx('//canvas')[0];
    let ctx = canvasNode.getContext("2d");
    ctx.clearRect(0,0,canvasNode.width,canvasNode.height);
    elementLists.forEach((elementPair) => {
      let elementList = elementPair[0];
      let color = elementPair[1];
      ctx.fillStyle = color;
      ctx.beginPath();
      for (const [key, el] of Object.entries(elementList)) {
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
    });
    ctx.stroke();
  };
}

function addScrollListener(elementLists) {
  window.addEventListener("scroll", scrollCallback(elementLists), false);
}

function handleIntersect(recEle){
  // console.log(recEle);
  return (entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        let te = recEle.elements[entry.target.tracker_id];
        if (te === undefined) {
          recEle.elements[entry.target.tracker_id] = entry.target;
          te = entry.target;
        }
        te.__tracker_isVisible = true;
        te.__tracker_intersectWidth = entry.intersectionRect.width;
        te.__tracker_intersectHeight = entry.intersectionRect.height;
        canvasRects[entry.target.tracker_id] = entry.intersectionRect;
      } else {
        recEle.elements[entry.target.tracker_id].__tracker_isVisible = false;
      }
    });
  }
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

initCanvas();
createMutationObserver();
mutationCallback(1,2);
// addScrollListener([[imgElements,'blue'], [textElements, 'red']]);