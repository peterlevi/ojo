var folder = '';
var image_count = 0;
var mode = 'image';
var search = '';
var current = '';
var current_elem;
var scroll_timeout;
var goto_visible_timeout;
var pending_add_timeouts = {};
var thumb_height = 120;

var selection_class = '.item';
var selected_file_per_class = {};

function log(msg) {
    // console.debug(msg);
}

function python(command) {
    log('Python command: ' + command);
    window.status = new Date().getTime() + '|' + command;
}

function set_mode(new_mode) {
    mode = new_mode;
    if (mode === 'folder') {
        scroll_to_selected();
    }
}

function set_thumb_height(new_thumb_height) {
    log('Setting thumb height: ' + new_thumb_height);
    thumb_height = new_thumb_height;
}

function toggle_fullscreen(fullscreen) {
    // Note: browsing transparency 14.04 vs 16.04
    //$('body').css('background', fullscreen ? 'rgba(77, 75, 69, 1)' : 'rgba(77, 75, 69, 0.9)')
}

function render_folders(data) {
    set_title(data.crumbs);

    _.map(data.categories, refresh_category);
    $('#folders').show();
}

function refresh_category(category) {
    var id = '#' + get_id(category.label);
    var elem = $(id);
    if (!elem.length) {
        add_folder_category(category.label);
    } else {
        $(id + ' .folder').remove();
    }

    var first = true;
    _.map(category.items, function(item) {
        var style = '';
        if (category.no_labels) {
            style = 'display: inline; ' + (first ? 'padding-right: 0' : 'padding: 0;');  //TODO we don't want inlined CSS
        }
        add_folder(category.label, item.label, item.path, item.filename, item.icon, style, item.nofocus);
        first = false;
    });
    if (category.no_labels) {
        $(id).append('<div></div>');
    }
}

function set_title(crumbs) {
    $('#title').html('');
    for (var i = 0; i < crumbs.length; i++) {
        var part = crumbs[i];
        $('<span class="crumb clickable match" file="' + encode_path(part.path) +
                '" filename="' + esc(part.name) + '">' + esc(part.name) + '</span>')
            .appendTo($("#title"));
        if (i > 0 && i < crumbs.length - 1) {
            $('<span>/</span>').appendTo($("#title"));
        }
    }
}

function get_id(s) {
    return s.replace(/[^a-z0-9]/gi,'')
}

function add_folder_category(label) {
    $("#folders").append(
        "<div class='folder-category' id='" + get_id(label) + "'>" +
        "<div class='folder-category-label'>" + esc(label) + "</div></div>");
}

function add_folder(category_label, label, path, filename, icon, style, nofocus) {
    var elem = $(_.template(
        "<div " +
        "   class='folder match' " +
        "   file='<%= path %>' " +
        "   filename='<%= filename %>' " +
        "   style='<%= style %>'>" +
        "<%= label %>" +
        "</div>")
    ({
        path: encode_path(path),
        filename: esc(filename),
        label: esc(label),
        style: style
    }));
    elem.addClass(path? (nofocus? 'clickable': 'selectable') : 'disabled');
    if (icon) {
        elem.prepend("<img class='folder-icon' src='" + encode_path(icon) + "'/>");
    }
    $("#" + get_id(category_label)).append(elem);
}

function add_group(label, is_first) {
    $(
        '<h2 class="group ' + (is_first ? 'first': 'non-first') + '" label="' + esc(label) + '">' +
        esc(label) +
        '</h2>'
    ).appendTo($('#images'));
}

function add_image_div(file, name, selected, show_caption, group, thumb, thumb_width) {
    if (file.indexOf(folder) !== 0) {
        return;
    }

    var html = _.template(
        "<div " +
        "   class='item selectable match' " +
        "   file='<%= file %>' " +
        "   filename='<%= name %>' " +
        "   group='<%= group %>' " +
        (thumb ? "with_thumb=true " : "") +
        "   style='width: <%= thumb_width %>; height: <%= thumb_height %>px'>" +
        "   <div class='holder' style='height: <%= thumb_height %>px'>" +
        (thumb ? "<img src='<%= thumb %>'/>" : "") +
        "   </div>" +
        "<div class='caption <%= caption_z %>'><%= name %></div>" +
        "</div>"
    )({
        file: encode_path(file),
        name: esc(name),
        group: esc(group),
        thumb: thumb ? encode_path(thumb) : '',
        thumb_width:
            thumb ? 'initial' :
            thumb_width ? thumb_width + 'px' :
            (thumb_height * 3/2) + 'px',
        thumb_height: thumb_height,
        caption_z: show_caption ? 'caption_above' : ''
    });

    var elem = $(html).toggleClass('selected', selected);
    if (search && !matches_search(elem)) {
        elem.addClass("nonmatch");
        elem.removeClass("match");
    }

    $('#images').append(elem);

    if (thumb) {
        update_progress();
    }

    if (selected) {
        current = encode_path(file);
        current_elem = elem[0];
        setTimeout(_.bind(scroll_to_selected, undefined, elem), 200);
    }
}

function set_image_count(count) {
    image_count = count;
}

function update_progress() {
    var done = $('.item[with_thumb=true]').length;
    var progress = done >= image_count ? 0 : Math.min(100, 100 * done / (image_count || 1));
    // (hide when done)
    $('#progress').width(progress + '%');
}

function add_image(file, thumb) {
    if (file.indexOf(folder) !== 0) {
        return;
    }

    clearTimeout(pending_add_timeouts[file]);
    var item = $(".item[file='" + encode_path(file) + "']");
    if (item.length) {
        item.attr('with_thumb', true).css('width', 'initial');
        item.find('.holder').html("<img src='" + encode_path(thumb) + "'/>");
        update_progress();
    } else {
        pending_add_timeouts[file] = setTimeout(function () {add_image(file, thumb)}, 200);
    }
}

function remove_image_div(file) {
    var to_remove = $(".item[file='" + encode_path(file) + "']");
    if (to_remove.hasClass('selected')) {
        var next = $(to_remove).next('.selectable');
        if (next.length === 0) {
            next = $('.selectable');
        }
        select(decode_path(next.attr('file')));
    }
    to_remove.remove();

    image_count = Math.max(0, image_count - 1);
    update_progress();
}

function change_folder(new_folder) {
    log('Changing to folder ' + new_folder);

    folder = new_folder;
    current = '';
    selection_class = '.item';
    selected_file_per_class = {};
    current_elem = undefined;
    search = '';
    clearTimeout(scroll_timeout);
    clearTimeout(goto_visible_timeout);

    _.map(_.values(pending_add_timeouts), clearTimeout);
    pending_add_timeouts = {};

    $('#search-field').val('');
    $('#title').html('');
    $('#folders').html('');
    $('#images').html('');
}

function set_dimensions(file, filename, dimensions, thumb_width) {
    $(".item[file='" + encode_path(file) + "']").attr('dimensions', dimensions).attr('filename', esc(filename));
    if (thumb_width) {
        $(".item[file='" + encode_path(file) + "']").css('width', thumb_width);
    }
    if (file === current) {
        $("#filename").html(filename);
        $("#dimensions").html(dimensions);
        $('#label').show();
    }
}

function show_error(error) {
    $('#filename').html(error);
}

function show_spinner(msg) {
    $('#filename').html('<img src="images/spinner.svg" class="spinner"/>' + msg);
}

function select(file, dontScrollTo, elem) {
    var el = elem || $(".match.selectable[file='" + encode_path(file) + "']").first();

    if (current === file && current_elem === el[0]) {
        return;
    }

    set_current_elem(el[0]);
    current = file;

    $("#filename").html(el.attr('filename') ? el.attr('filename') : '&nbsp;');
    $("#dimensions").html(el.attr('dimensions') ? el.attr('dimensions') : '&nbsp;');

    log("Selecting " + file);
    python("ojo-select:" + file);
    if (!dontScrollTo) {
        scroll_to_selected(el);
    }
}

function scroll_to_selected(el) {
    log('Scroll to selected');
    el = el || $('.selected');
    if (el.length) {
        var baseDelta = el.hasClass('item') ? thumb_height : 40;
        var container = el.closest('.scroll-container');
        var scrollTop = container.scrollTop();
        var top = scrollTop + el.position().top;
        var containerHeight = container.height();

        var scrollTo;
        if (top > scrollTop + containerHeight - baseDelta * 2) {
            scrollTo = top - containerHeight + baseDelta * 2;
        } else if (top < scrollTop + baseDelta * 1.2) {
            scrollTo = Math.max(0, top - baseDelta * 1.2);
        }

        if (!_.isUndefined(scrollTo)) {
            container.scrollTop(scrollTo);
        }
    }
}

function set_current_elem(new_current_elem) {
    if (current_elem) {
        var current_sel_class = $(current_elem).hasClass('folder') ? '.folder' : '.item';
        selected_file_per_class[current_sel_class] = current;
    }
    current_elem = new_current_elem;
    $(".selectable").removeClass('selected');
    if (new_current_elem) {
        selection_class = $(new_current_elem).hasClass('folder') ? '.folder' : '.item';
        $(new_current_elem).addClass('selected');
    } else {
        selection_class = '.item';
    }
}

function goto(elem, dontScrollTo) {
    if (elem && elem.length > 0) {
        var file = decode_path(elem.attr('file'));
        select(file, dontScrollTo, elem);
    }
}

function get_next_in_direction(elem, direction) {
    var current = elem.offset().top + (direction < 0 ? -10 : elem.height());
    var applicable = $('.selectable.match' + selection_class).filter(function() {
        var candidate = $(this).offset().top;
        return direction < 0 ?
            candidate < current && candidate > current - 3*thumb_height :
            candidate > current && candidate < current + 3*thumb_height;
    });
    if (applicable.length > 0) {
        return $(_.min(applicable, function(el) {
            return distance($(el), elem);
        }));
    } else {
        return null;
    }
}

function goto_visible(first_or_last, onlyClass, immediate) {
    clearTimeout(goto_visible_timeout);

    function _go() {
        for (var attempt = 0; attempt <= 1; attempt++) {
            var visible = _.filter(
                $('.selectable.match' + (onlyClass ? onlyClass : (attempt === 0 ? selection_class : ''))),
                function(x) {
                    var container = $(x).closest('.scroll-container');
                    var scrollTop = container.scrollTop();
                    return $(x).position().top >= -5 &&
                        $(x).position().top + $(x).height() < container.height() + 5;
                }
            );
            if (visible.length) {
                break;
            }
        }
        var file = decode_path($(first_or_last ? _.first(visible) : _.last(visible)).attr('file'));
        select(file, true);
        python("ojo-select:" + file);
    }

    goto_visible_timeout = setTimeout(_go, immediate ? 10 : 100);
}

function on_key(key) {
    var sel = $('.selected');
    if (key === 'Tab') {
        var new_selection_class = selection_class === '.item' ? '.folder' : '.item';
        var new_file = selected_file_per_class[new_selection_class];
        if (new_file) {
            select(new_file);
        } else {
            var elem = $('.selectable.match' + new_selection_class);
            if (elem.length) {
                goto($(elem[0]));
                selection_class = new_selection_class;
            }
        }
    } else if (key === 'Up' || key === 'Down') {
        goto(get_next_in_direction(sel, key === 'Up' ? -1 : 1), false);
    } else if (key === 'Right') {
        if (selection_class === '.item') {
            var next = sel.nextAll('.selectable.match' + selection_class);
            goto(next.length ? $(next[0]) : null);
        }
    } else if (key === 'Left') {
        if (selection_class === '.item') {
            var prev = sel.prevAll('.selectable.match' + selection_class);
            goto(prev.length ? $(prev[0]) : null);
        }
    } else if (key === "Page_Up" || key === "Page_Down") {
        var direction = key === "Page_Up" ? -1 : 1;
        var container = sel.closest('.scroll-container');
        container.scrollTop(container.scrollTop() + direction * container.outerHeight());

        setTimeout(function() {
            if (container.scrollTop() === 0 ||
                container.scrollTop() + container.outerHeight() === container.prop('scrollHeight') ||
                container.scrollTop() + container.height() === container.prop('scrollHeight')
            ) {
                // reached the top or bottom
                goto_visible(key === "Page_Up", sel.hasClass('item') ? '.item' : '.folder', true);
            } else {
                goto_visible(true, sel.hasClass('item') ? '.item' : '.folder', false);
            }
        }, 0);
    } else if (key === "Home") {
        goto($(selection_class + ".selectable.match:first"));
    } else if (key === "End") {
        goto($(selection_class + ".selectable.match:last"));
    } else if (key === 'BackSpace') {
        python('ojo-handle-key:' + key)
    } else if (key === 'Escape') {
        python('ojo-handle-key:' + key)
    }
}

function matches_search(elem) {
    var nbsp = new RegExp(String.fromCharCode(160), 'g');
    var filename = (elem.attr('filename') || '').replace(nbsp, ' ');
    var file = (elem.attr('file') || '').replace(nbsp, ' ');
    var group = (elem.attr('group') || '').replace(nbsp, ' ');

    var words = search.split(' ').filter(Boolean);

    return _.every(words, function (word) {
        var wordLow = word.toLowerCase();
        return (
            (filename && filename.toLowerCase().indexOf(wordLow) >= 0) ||
            (group && group.toLowerCase().indexOf(wordLow) >= 0) ||
            (file && file.substring(0, 'command:'.length) === 'command:' &&
                file.substring('command:'.length + 1).toLowerCase().indexOf(wordLow) >= 0)
        );
    });
}

function on_search() {
    log('Searching for ' + search);
    python('ojo-search:' + search);
    $('.selectable')
        .filter(function() {return !matches_search($(this))})
        .removeClass("match")
        .addClass("nonmatch");
    var matches = $('.selectable').filter(function() {return matches_search($(this))});
    matches.removeClass("nonmatch").addClass("match");

    // hide/show groups
    var firstGroup = true;
    $('.group').map(function() {
        var g = $(this);
        var keep = matches.filter(function () {
            var m = $(this);
            return m.attr('group') === g.attr('label');
        }).length > 0;
        g.toggleClass('match', keep).toggleClass('nonmatch', !keep);
        if (keep) {
            g.toggleClass('first', firstGroup);
            firstGroup = false;
        } else {
            g.removeClass('first');
        }
    });

    var sel = $('.selected');
    if (matches.length && (sel.length === 0 || !_.contains(matches, sel[0]))) {
        select(decode_path($(matches[0]).attr('file')));
    } else {
        scroll_to_selected();
    }

    setTimeout(function() { scroll_to_selected() }, 200);

    clearTimeout(scroll_timeout);
    scroll_timeout = setTimeout(on_images_scroll, 200);
}

function distance(el1, el2) {
    var dy = $(el1).offset().top - $(el2).offset().top;
    var dx = $(el1).offset().left - $(el2).offset().left;
    return dx*dx + dy*dy
}

function on_images_scroll() {
    var files = _.map(_.filter($('.item.match'), function(x) {
        var $x = $(x);
        return !$x.attr('with_thumb') && $x.position().top + $x.height() >= 0;
    }), function(x) { return decode_path($(x).attr('file')) });
    python('ojo-priority:' + JSON.stringify(files));
}

var entityMap = {
    "&": "&amp;",
    " ": "&nbsp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': '&quot;',
    "'": '&#39;',
    "/": '&#x2F;'
};

function esc(string) {
    return String(string).replace(/[&<>"'\/ ]/g, function (s) {
        return entityMap[s];
    });
}

function encode_path(path) {
    return path;
}

function decode_path(path) {
    return path;
}

function on_clickable(event) {
    if (mode !== 'folder') {
        event.preventDefault();
        return;
    }
    python("ojo:" + decode_path($(this).attr('file')));
}


function toggle_captions(visible) {
    $('.caption').toggleClass('caption_above', visible);
    select('command:captions:' + (visible ? 'false' : 'true'));
}

function toggle_search(visible) {
    $('#search-box').css('opacity', visible ? 1 : 0);
    if (visible) {
        setTimeout(function () {
            $('#search-field').focus();
        }, 10);
        // schedule one more to be sure, otherwise we miss the focus sometimes
        setTimeout(function () {
            $('#search-field').focus();
        }, 100);
    } else if (search !== '') {
        search = '';
        $('#search-field').val('');
        on_search();
    }
}

$(function() {
    change_folder('');

    $(document).contextmenu(function(event) {
        event.preventDefault();
    });

    $(document).keydown(function(e) {
        $('#search-field').focus();
        if (mode !== 'folder') {
            e.preventDefault();
            return;
        }
        if (e.keyCode === 9 || e.keyCode === 27 || (e.keyCode >= 35 && e.keyCode <= 40)) {
            // suppress esc, arrows, home, end (we handle those in Python)
            e.preventDefault();
            return;
        }
    });

    $('#images').scroll(function() {
        clearTimeout(scroll_timeout);
        scroll_timeout = setTimeout(on_images_scroll, 200);
    });

    $(window).resize(function() {
        if (current) {
            select(current);
        }
    });

    $(document).on('click', '.selectable, .clickable', on_clickable);

    $('#search-field').on('input', function() {
        if ($(this).val() !== search) {
            search = $(this).val();
            on_search();
        }
    });

    $('#search-field').keydown(function(e) {
        if (e.keyCode === 27 || (e.keyCode >= 35 && e.keyCode <= 40)) {
            // suppress esc, arrows, home, end (we use them for pics navigation)
            e.preventDefault();
        }
    });
});
