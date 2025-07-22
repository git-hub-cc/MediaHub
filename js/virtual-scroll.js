// virtual-scroll.js

export class InfiniteScroller {
    // =========================================================================
    // == 区域: 构造函数与属性初始化
    // =========================================================================

    /**
     * 创建一个无限滚动器实例。
     * @param {object} config - 配置对象。
     * @param {HTMLElement} config.container - 用于渲染内容的容器元素。
     * @param {Array<any>} config.dataArray - 需要分批加载的完整数据数组。
     * @param {Function} config.renderBatchFunc - 用于渲染一批数据的回调函数，接收 (batch, offset) 两个参数。
     * @param {number} [config.batchSize=80] - 每次加载的数据项数量。
     * @param {HTMLElement} config.loadingIndicator - 用于显示加载状态的元素。
     */
    constructor({ container, dataArray, renderBatchFunc, batchSize = 80, loadingIndicator }) {
        this.container = container;
        this.dataArray = dataArray;
        this.renderBatchFunc = renderBatchFunc;
        this.batchSize = batchSize;
        this.loadingIndicator = loadingIndicator;

        this.offset = 0; // 当前已加载数据在总数组中的偏移量
        this.isLoading = false; // 加载状态标志，防止重复加载
    }

    // =========================================================================
    // == 区域: 公共方法
    // =========================================================================

    /**
     * 加载并渲染下一批数据。
     */
    loadNextBatch() {
        // 如果正在加载或所有数据已加载完毕，则不执行任何操作
        if (this.isLoading || this.isFinished()) {
            return;
        }

        this.isLoading = true;
        this.setLoadingState(true);

        // 使用 setTimeout 模拟一个微小的延迟。
        // 目的是为了确保浏览器有足够的时间渲染 "正在加载" 的提示信息，
        // 尤其是在数据处理速度极快的情况下，这能改善用户体验。
        setTimeout(() => {
            const batch = this.dataArray.slice(this.offset, this.offset + this.batchSize);
            this.renderBatchFunc(batch, this.offset);
            this.offset += batch.length;

            this.isLoading = false;
            this.setLoadingState(false);

            // 如果加载完这一批后所有数据都已加载，则显示完成信息
            if (this.isFinished()) {
                this.showFinishedMessage();
            }
        }, 100);
    }

    /**
     * 重置滚动器状态，清空容器内容，为新的数据源做准备。
     */
    reset() {
        this.offset = 0;
        this.isLoading = false;
        this.container.innerHTML = '';
        this.setLoadingState(false);
    }

    // =========================================================================
    // == 区域: 内部状态检查与管理
    // =========================================================================

    /**
     * 检查是否所有数据都已加载完成。
     * @returns {boolean} 如果已全部加载，返回 true。
     */
    isFinished() {
        return this.offset >= this.dataArray.length;
    }

    /**
     * 控制加载指示器的显示状态和文本。
     * @param {boolean} show - true 表示显示加载中，false 表示隐藏。
     * @private
     */
    setLoadingState(show) {
        if (!this.loadingIndicator) return;

        this.loadingIndicator.style.display = show ? 'block' : 'none';
        if (show) {
            this.loadingIndicator.textContent = '正在加载更多...';
        }
    }

    /**
     * 当所有数据加载完毕时，显示最终提示信息。
     * @private
     */
    showFinishedMessage() {
        if (!this.loadingIndicator) return;

        this.loadingIndicator.style.display = 'block';
        this.loadingIndicator.textContent = '已加载全部内容';
    }
}