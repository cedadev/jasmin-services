(function($) {
    // Code to enable collapsible inlines
    $(function() {
        // Collapse visible fieldsets to start
        $('.inline-related:not(.empty-form):not(:has(.errorlist)) h3').siblings().hide();
        // Change the cursor on inline headings
        $('head').append('<style>.inline-related h3 { cursor: pointer; }</style>');
        $(document).on('click', '.inline-related h3', function(e) {
            var $h3 = $(this);
            // Ignore clicks on the checkbox
            if( $(e.target).parent('span.delete').length > 0 ) return;
            $h3.siblings().toggle();
        });
    });
})(django.jQuery);
