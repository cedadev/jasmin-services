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
    // Code to turn the polymorphic list into a select
    $(function() {
        // When the add row is added, modify it
        $('.polymorphic-add-choice').initialize(function() {
            var $add_row = $(this);
            var $type_menu = $add_row.find('.polymorphic-type-menu');
            $type_menu.hide();
            // Build a select from the items in the polymorphic-type-menu
            var $select = $('<select></select>').css({ 'margin-right' : '5px' });
            $type_menu.find('li a').each(function() {
                var $this = $(this);
                $select.append('<option value="' + $this.data('type') + '">' + $this.text() + '</option>');
            });
            $add_row.prepend($select);
            // Re-purpose the add link
            $add_row.children('a').off('click').on('click', function() {
                // Simulate a click of the menu item corresponding to the current
                // selection
                $add_row.find('li a[data-type="' + $select.val() + '"]').click();
            }).text('Add field');
        });
    });
})(django.jQuery);
