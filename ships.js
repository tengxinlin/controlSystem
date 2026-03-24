// 定义Ship类
class Ship {
    constructor(data = {}) {
        this.MMSI = data.MMSI || '';              // MMSI编码
        this.name = data.name || '未知船舶';       // 船名
        this.lat = data.lat || 0;                 // 纬度
        this.lng = data.lng || 0;                 // 经度
        this.heading = data.heading || 0;         // 航向角（0-360度）
        this.speed = data.speed || 0;             // 航速（节）
        this.course = data.course || 0;           // 航向（真北方向）
        this.updateTime = data.updateTime || new Date().toISOString();  // 更新时间
        this.previous = data.previous || null;    // 上一次的ship信息
        this.status = data.status || 'normal';    // 船舶状态,上水up，下水down，停靠docker，特殊se
        this.shipType = data.shipType || 'cargo'; // 船舶类型
    }

    // 更新船舶信息
    update(newData) {
        // 保存当前数据到previous
        this.previous = {
            MMSI: this.MMSI,
            name: this.name,
            lat: this.lat,
            lng: this.lng,
            heading: this.heading,
            speed: this.speed,
            course: this.course,
            updateTime: this.updateTime,
            status: this.status,
            shipType: this.shipType
        };

        // 更新当前数据
        Object.assign(this, newData);
        this.updateTime = new Date().toISOString();
        return this;
    }

    // 获取位置坐标
    getPosition() {
        return [this.lat, this.lng];
    }

    // 计算与上一次位置的距离（简化的距离计算）
    getDistanceFromPrevious() {
        if (!this.previous) return 0;

        // 使用Haversine公式计算距离（公里）
        const R = 6371; // 地球半径，单位公里
        const dLat = this.toRad(this.lat - this.previous.lat);
        const dLng = this.toRad(this.lng - this.previous.lng);
        const a =
            Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(this.toRad(this.lat)) * Math.cos(this.toRad(this.previous.lat)) *
            Math.sin(dLng/2) * Math.sin(dLng/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }

    // 度转弧度
    toRad(degrees) {
        return degrees * Math.PI / 180;
    }

    // 转换为JSON格式
    toJSON() {
        return {
            MMSI: this.MMSI,
            name: this.name,
            lat: this.lat,
            lng: this.lng,
            heading: this.heading,
            speed: this.speed,
            course: this.course,
            updateTime: this.updateTime,
            status: this.status,
            shipType: this.shipType,
            previous: this.previous
        };
    }

    // 克隆船舶对象
    clone() {
        return new Ship(this.toJSON());
    }
}
// 将 Ship 暴露给全局
window.Ship = Ship;
