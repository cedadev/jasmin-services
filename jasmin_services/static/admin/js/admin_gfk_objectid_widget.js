(function($) {
    // Implement windowopened and windowclosed events
    // To implement windowopen, we need to override window.open
    // The unload event doesn't fire in the parent window, so to implement windowclose,
    // we need to keep a register of open windows and poll them
    var openWindows = new Map();
    var windowOpen = window.open;
    window.open = function() {
        var win = windowOpen.apply(this, arguments);
        openWindows.set(win.name, win);
        $(window).trigger(
            $.Event('windowopened', { 'windowName': win.name, 'window': win })
        );
        return win;
    };
    setInterval(function() {
        // Fire the closed event for each window in closed and built a replacement
        // set of open windows
        var stillOpen = new Map();
        openWindows.forEach(function(win, name) {
            if( win.closed ) {
                $(window).trigger(
                    $.Event('windowclosed', { 'windowName': name, 'window': win })
                );
            } else {
                stillOpen.set(name, win);
            }
        });
        openWindows = stillOpen;
    }, 300);

    $(function() {
        // Add related lookup links and placeholders for
        $('.gfk-objectid').after(function() {
            return [
                '<a href="#" class="related-lookup" id="lookup_id_' + $(this).attr('name') + '"></a>',
                '&nbsp;&nbsp;&nbsp;',
                '<span class="gfk-object-text" style="font-weight: bold;"></span>'
            ];
        });
        // Prevent any actions on related lookup links where the href is #
        $('body').on('django:lookup-related', '.related-lookup[href="#"]', function(e) {
            e.preventDefault();
            alert('Lookup is not available for selected content type.');
        });
        // Listen for changes to contenttype selection
        $('body').on('change', '.gfk-contenttype', function() {
            var $this = $(this);
            var ctId = $this.val();
            // Find the corresponding objectid field
            var $objectid = $this.closest('fieldset').find('.gfk-objectid').first();
            // Update the related lookup link based on the selected content type
            $objectid.siblings('.related-lookup').attr(
                'href',
                $objectid.data('ctype-url-map')[ctId] || '#'
            );
            // If the current value is a change from the previous value, reset
            // the object id
            if( ctId !== $this.data('previous') ) {
                $this.data('previous', ctId);
                $objectid.val(null);
                $objectid.trigger('change');
            }
        });
        $('.gfk-contenttype').each(function() { $(this).data('previous', $(this).val()); })
        $('.gfk-contenttype').trigger('change');
        // Listen for changes to objectid selection
        $('body').on('change', '.gfk-objectid', function() {
            var $this = $(this);
            // Find the content type id and object id
            var ctId = $this.closest('fieldset').find('.gfk-contenttype').first().val();
            var objId = $this.val();
            // If this is actually a change, update the placeholder
            if( objId !== $this.data('previous') ) {
                $this.data('previous', objId);
                var $placeholder = $this.siblings('.gfk-object-text');
                $placeholder.text(null);
                if( ctId && objId )
                    $.get($this.data('object-text-url'), { 'ct_id': ctId, 'pk': objId })
                        .done(function(data) { $placeholder.text(data); })
                        .fail(function() { $placeholder.text(null); });
            }
        });
        $('.gfk-objectid').trigger('change');
        // Listen for windows being closed to trigger the change event of the
        // corresponding objectid field
        $(window).on('windowclosed', function(e) {
            var id = window.windowname_to_id(e.windowName);
            $('.gfk-objectid#' + id).trigger('change');
        });
    });
})(django.jQuery);
