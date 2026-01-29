
function helper() {
    console.log("I am helper");
}

const arrowHelper = () => {
    return "arrow";
}

class Service {
    doWork() {
        return true;
    }
}

module.exports = { helper, arrowHelper, Service };
