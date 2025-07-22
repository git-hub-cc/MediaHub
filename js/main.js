// app.js

import { InfiniteScroller } from './virtual-scroll.js';
import * as data from './data.js';
import * as ui from './ui.js';

/**
 * 检查是否需要加载更多内容以填满视口。
 * 如果当前内容不足以产生滚动条，则继续加载，直到出现滚动条或数据加载完毕。
 */
function fillViewport() {
    // 获取滚动容器和内容高度
    const container = document.documentElement; // 通常是整个页面

    // 循环条件：
    // 1. 内容高度小于等于视口高度（没有滚动条）
    // 2. 并且滚动器中还有未加载的数据
    while (
        container.scrollHeight <= container.clientHeight &&
        data.scroller.instance.hasMore()
        ) {
        console.log('视口未填满，正在主动加载下一批数据...');
        data.scroller.instance.loadNextBatch();
    }
}


/**
 * 应用初始化总函数
 */
async function initialize() {
    ui.ui.loadingIndicator.style.display = 'block';
    ui.ui.loadingIndicator.textContent = '正在初始化应用...';

    try {
        // 1. 加载所有数据和设置
        await data.initializeData();

        // 2. 根据加载的数据状态更新UI
        ui.updateInitialUI();

        // 3. 初始化无限滚动器
        data.scroller.instance = new InfiniteScroller({
            container: ui.ui.movieGrid,
            dataArray: data.allMovies,
            renderBatchFunc: ui.appendMovies,
            batchSize: data.BATCH_SIZE,
            loadingIndicator: ui.ui.loadingIndicator
        });

        // 4. 设置所有UI事件监听器
        ui.setupEventListeners();

        // 5. 加载第一批内容
        data.scroller.instance.loadNextBatch();

        // 6. 【BUG修复】检查并填充视口，确保初始内容足以触发滚动
        // 使用 setTimeout 确保在 DOM 渲染完成后执行检查
        setTimeout(fillViewport, 100);

        ui.ui.loadingIndicator.style.display = 'none';

    } catch (error) {
        console.error("应用初始化失败:", error);
        ui.ui.loadingIndicator.textContent = `加载失败: ${error.message}`;
        ui.showToast(`应用启动失败: ${error.message}`, 10000);
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', initialize);