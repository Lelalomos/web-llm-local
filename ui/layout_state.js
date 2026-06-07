window.COMPACT_LAYOUT_MAX_WIDTH = 900;

window.isCompactLayout = function isCompactLayout(viewportWidth) {
    return Number(viewportWidth) <= window.COMPACT_LAYOUT_MAX_WIDTH;
};

window.shouldCloseSidebarAfterAction = function shouldCloseSidebarAfterAction(viewportWidth) {
    return window.isCompactLayout(viewportWidth);
};
