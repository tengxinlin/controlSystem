// 使用Map存储船舶，以MMSI为键
// ShipManager.js - 导入Ship类

// 船舶标记管理器
  class ShipMarkerManager {
    constructor() {
        this.ships = new Map();
    }

    // 添加或更新船舶
    addOrUpdateShipMarker(shipData) {
        const mmsi = shipData.MMSI;

        if (this.ships.has(mmsi)) {
            // 更新现有船舶
            const existingShip = this.ships.get(mmsi);
            existingShip.update(shipData);
            return existingShip;
        } else {
            // 添加新船舶
            const newShip = new Ship(shipData);
            this.ships.set(mmsi, newShip);
            return newShip;
        }

    }

    // 创建船舶图标
    createShipIcon(ship) {
                    var size = 15;
                    var html = '<div style="' +
                        'width: 0; height: 0;' +
                        'border-left: ' + size + 'px solid transparent;' +
                        'border-right: ' + size + 'px solid transparent;' +
                        'border-bottom: ' + size + 'px solid ' + color + ';' +
                        'transform: rotate(' + angle + 'deg);' +
                        'filter: drop-shadow(1px 1px 1px rgba(0,0,0,0.5));' +
                        '"></div>';

                    return L.divIcon({
                        html: html,
                        iconSize: [30, 30],
                        iconAnchor: [15, 15],
                        className: 'ship-icon'
                    });
                }

    // 移除船舶
    removeShip(mmsi) {
        return this.ships.delete(mmsi);
    }

    // 获取船舶
    getShip(mmsi) {
        return this.ships.get(mmsi);
    }

    // 获取所有船舶
    getAllShips() {
        return Array.from(this.ships.values());
    }

    // 根据名称搜索船舶
    searchByName(name) {
        const results = [];
        for (const ship of this.ships.values()) {
            if (ship.name.includes(name)) {
                results.push(ship);
            }
        }
        return results;
    }

    // 清除所有船舶
    clearAll() {
        this.ships.clear();
    }

    // 获取船舶数量
    getCount() {
        return this.ships.size;
    }
}
