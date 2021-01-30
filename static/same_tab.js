"use strict";
// "_blank|_self|_parent|_top|framename"; "framename" should not start with "_"
// - list of iframe names only contains the names of iframes and not the names
// of windows in other tabs that could be targets
// - list of iframe names is not updated if an iframe's name changes

(function() {
    const sameTab = {
        converted: false,
        observer: null,
        iframeNameList: [],
        index: -1,

        mutationObserverFunction: function(mutations, observer) {
            let target;

            sameTab.observer.disconnect();
            for (let mutation of mutations) {
                target = mutation.target;
                if (!document.contains(target)) continue;
                switch (mutation.type) {
                    case "attributes":
                        if (mutation.attributeName !== "target" ||
                            target.tagName !== "A") break;
                        target.onclick = (!target.target ||
                            target.target[0] === '_') ? null : sameTab.doNamedTarget;
                        if (target.target !== "_blank" || mutation.oldValue === "_top") break;
                        target.target = "_top";
                        break;
                    case "childList":
                        for (let node of mutation.addedNodes) {
                            if (node.parentNode !== target || node.nodeType !=
                                document.ELEMENT_NODE) continue;
                            sameTab.convertLinks(node);
                        }
                        break;
                }
            }
            sameTab.observeDocument();
        },

        observeDocument: function() {
            sameTab.observer.observe(document, {
                childList: true,
                subtree: true,
                characterData: false,
                attributes: true,
                attributeOldValue: true,
                attributeFilter: ["target"]
            });
        },

        convertDocument: function(evnt) {
            sameTab.convertLinks(document);
            sameTab.observer = new MutationObserver(sameTab.mutationObserverFunction);
            sameTab.observeDocument();
            sameTab.converted = true;
        },

        // When a link with a named target is clicked, change the target to "_top"
        // unless the name is in the list of iframe names.
        doNamedTarget: function({
            target
        }) {
            // First make sure the iframe's own name is correct.
            if (sameTab.index !== -1) {
                sameTab.iframeNameList[sameTab.index] = window.name;
            }
            // Do nothing if the target name is in the list of window names.
            if (sameTab.iframeNameList.indexOf(target.target) !== -1) return;
            target.target = "_top";
        },

        // If the link target is "_blank" change it to "_top". If it is a name
        // which does not begin with "_" set the link's click event handler so
        // the list of iframe names can be checked for the target when the link is
        // clicked.
        convertLinks: function(node) {
            let list;

            list = [...node.querySelectorAll(
                'a[target="_blank"],a[target]:not([target^="_"])')];
            if (node.tagName === "A" && node.target &&
                (node.target === "_blank" || node.target[0] !== "_")) {
                list.push(node);
            }
            for (let item of list) {
                if (item.target === "_blank") {
                    item.target = "_top";
                } else {
                    item.onclick = sameTab.doNamedTarget;
                }
            }
        }
    };

    // Top frame
    function doTop() {
        const frame = {
            iframeList: [],
            convertAllLinks: false,
            hostname: null,

            // Delete an item from the list of iframes.
            removeIframe: function(id) {
                let indx;

                indx = frame.iframeList.findIndex(item => item.id === id);
                if (indx == -1) return;
                frame.iframeList.splice(indx, 1);
                sameTab.iframeNameList.splice(indx, 1);
            },

            sendIframeList: function() {
                let origin, source, item;

                item = {
                    senderId: "sameTabExtensionTop",
                    message: "nameList",
                    iframeNameList: sameTab.iframeNameList,
                    index: frame.iframeList.length
                };
                while (item.index--) {
                    ({
                        origin,
                        source
                    } = frame.iframeList[item.index]);
                    if (origin === "null") {
                        origin = "*";
                    }
                    try {
                        source.postMessage(item, origin);
                    } catch (err) {
                        console.warn(err.message);
                    }
                }
            },

            checkLists: function(items) {
                if (!items.settingsInitialized) {
                    console.warn("Stored data missing.");
                } else if (items.convertLinks && !(items.useWhitelist &&
                        items.whitelist.indexOf(frame.hostname) == -1) &&
                    items.blacklist.indexOf(frame.hostname) == -1) {
                    frame.convertAllLinks = true;
                    frame.sendIframeList();
                    if (document.readyState === "interactive" ||
                        document.readyState === "complete") {
                        sameTab.convertDocument(null);
                    } else {
                        document.addEventListener("DOMContentLoaded",
                            sameTab.convertDocument);
                    }
                    return;
                }
                window.removeEventListener("message", frame.windowMessages);
                frame.iframeList.length = 0;
                sameTab.iframeNameList.length = 0;
            },

            getHostname: function() {
                switch (location.protocol) {
                    case "file:":
                        return `file://${location.hostname}${location.pathname}`;
                        break;
                    case "http:":
                    case "https:":
                        return location.hostname;
                        break;
                }
                return null;
            },

            windowMessages: function({
                origin,
                source,
                data
            }) {
                let item, indx;

                if (!data || data.senderId !== "sameTabExtensionIframe") return;
                switch (data.message) {
                    case "windowUnloaded":
                        frame.removeIframe(data.id);
                        frame.sendIframeList();
                        break;
                    case "contentLoaded":
                        if ((source || {})
                            .top !== window) return;
                        item = {
                            origin: origin,
                            source: source,
                            id: data.id
                        };
                        indx = frame.iframeList.findIndex(({
                            id
                        }) => id === data.id);
                        if (indx == -1) {
                            frame.iframeList.push(item);
                            sameTab.iframeNameList.push(data.frameName);
                        } else {
                            frame.iframeList[indx] = item;
                            sameTab.iframeNameList[indx] = data.frameName;
                        }
                        if (!frame.convertAllLinks) return;
                        frame.sendIframeList();
                        break;
                }
            }
        };

        frame.hostname = frame.getHostname();
        if (frame.hostname) {
            window.addEventListener("message", frame.windowMessages);
            chrome.storage.local.get(null, frame.checkLists);
        }
    }

    // Iframes
    function doFrame() {
        const frame = {
            id: Math.random(),

            events: {
                // Accept messages from the top window only.
                message: function({
                    source,
                    data
                }) {
                    if (source !== top) return;
                    if (!data || data.senderId !== "sameTabExtensionTop" ||
                        data.message !== "nameList") return;
                    sameTab.iframeNameList = data.iframeNameList;
                    sameTab.index = data.index;
                    if (sameTab.converted) return;
                    sameTab.convertDocument(null);
                },

                // Tell top window that the window has unloaded
                unload: function(evnt) {
                    let origin;

                    try {
                        origin = top.location.origin;
                    } catch (err) {
                        origin = "*";
                    }
                    top.postMessage({
                        senderId: "sameTabExtensionIframe",
                        message: "windowUnloaded",
                        id: frame.id
                    }, origin);
                }
            },

            // Post the window's name to the top window.
            contentLoaded: function(evnt) {
                let origin;

                window.addEventListener("message", frame.events.message);
                window.addEventListener("unload", frame.events.unload);
                try {
                    origin = top.location.origin;
                } catch (err) {
                    origin = "*";
                }
                top.postMessage({
                    senderId: "sameTabExtensionIframe",
                    message: "contentLoaded",
                    frameName: window.name,
                    id: frame.id
                }, origin);
            }
        };

        document.addEventListener("DOMContentLoaded", frame.contentLoaded);
    }

    ((window === top) ? doTop : doFrame)();
}());