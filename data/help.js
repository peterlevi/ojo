function log(msg) {
    // console.debug(msg);
}

function python(command) {
    log('Python command: ' + command);
    window.status = new Date().getTime() + '|' + command;
}

$(function() {
    $('#close').click(function() {
        python('ojo-close-overlay:help.html');
    });
});