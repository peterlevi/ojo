function log(msg) {
    // console.debug(msg);
}

function python(command) {
    log('Python command: ' + command);
    window.status = new Date().getTime() + '|' + command;
}

$(function() {
    $('#left').click(function() {
        python('ojo-left:');
    });
    $('#right').click(function() {
        python('ojo-right:');
    });
    $('#browse').click(function() {
        python('ojo-browse:');
    });
});