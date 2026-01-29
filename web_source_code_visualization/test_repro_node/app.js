
const { helper, arrowHelper, Service } = require('./utils');

function main() {
    helper();
    arrowHelper();
    
    const s = new Service();
    s.doWork();
}
