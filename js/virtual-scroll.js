export class InfiniteScroller {
    constructor({ container, dataArray, renderBatchFunc, batchSize = 80, loadingIndicator }) {
        this.container = container;
        this.dataArray = dataArray;
        this.renderBatchFunc = renderBatchFunc;
        this.batchSize = batchSize;
        this.loadingIndicator = loadingIndicator;
        this.offset = 0;
        this.isLoading = false;
    }

    /**
     * 加载下一批数据并渲染到容器中。
     */
    loadNextBatch() {
        if (this.isLoading || this.isFinished()) {
            return;
        }

        this.isLoading = true;
        this.setLoadingState(true);

        // 使用setTimeout模拟网络延迟，让加载指示器有机会显示
        setTimeout(() => {
            const batch = this.dataArray.slice(this.offset, this.offset + this.batchSize);
            this.renderBatchFunc(batch, this.offset);
            this.offset += batch.length;

            this.isLoading = false;
            this.setLoadingState(false);

            if (this.isFinished()) {
                this.showFinishedMessage();
            }
        }, 100); // 短暂延迟
    }

    /**
     * 重置滚动器状态，清空容器内容。
     */
    reset() {
        this.offset = 0;
        this.isLoading = false;
        this.container.innerHTML = '';
        this.setLoadingState(false);
    }

    /**
     * 检查是否所有数据都已加载。
     * @returns {boolean}
     */
    isFinished() {
        return this.offset >= this.dataArray.length;
    }

    /**
     * 控制加载指示器的显示状态。
     * @param {boolean} show - 是否显示加载指示器
     */
    setLoadingState(show) {
        if (!this.loadingIndicator) return;
        this.loadingIndicator.style.display = show ? 'block' : 'none';
        if (show) {
            this.loadingIndicator.textContent = '正在加载更多...';
        }
    }

    /**
     * 显示数据全部加载完毕的提示信息。
     */
    showFinishedMessage() {
        if (!this.loadingIndicator) return;
        this.loadingIndicator.style.display = 'block';
        this.loadingIndicator.textContent = '已加载全部内容';
    }
}