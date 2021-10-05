$('.reason-stack').show();
// Stuff for rotating reasons
var show_reason = function($reason) {
    if( $reason.length > 0 ) {
        $('.reason').not($reason).hide();
        $reason.show();
    }
};
var prev_reason = function() { show_reason($('.reason:visible').prev()); return false; };
var next_reason = function() { show_reason($('.reason:visible').next()); return false; }
var n_reasons = {{ rejected|length }};
show_reason($('.reason:last-child'));
// Inject the previous/next reason buttons
$('.reason').each(function(i, el) {
    if( i > 0 ) {
        var $link = $('<a href="#" title="Previous reason"><i class="fa fa-fw fa-caret-left"></i></a>');
        $link.click(prev_reason);
        $(el).find('.reason-number').prepend($link);
    }
    if( i < n_reasons - 1 ) {
        var $link = $('<a href="#" title="Next reason"><i class="fa fa-fw fa-caret-right"></i></a>');
        $link.click(next_reason);
        $(el).find('.reason-number').append($link);
    }
});

// Reset the hiding of form-groups except for those we are worried about
$('.form-group').not('.reason, :has([name^="expires"]), :has([name$="_reason"])').show();
// Constants used in the function below
var YES = 'APPROVED', NO = 'REJECTED', NO_INCOMPLETE = 'INCOMPLETE', CUSTOM_DATE = '7';
// This function makes sure only fields which are needed are shown
var toggle_fields = function() {
    var state = $('[name="state"]').val();
    var expires = $('[name="expires"]').val();
    $('[name="expires"]').closest('.form-group')[state == YES ? 'show' : 'hide']();
    var show_custom = ( state == YES && expires == CUSTOM_DATE );
    $('[name="expires_custom"]').closest('.form-group')[show_custom ? 'show' : 'hide']();
    $('[name$="_reason"]').closest('.form-group')[( state == NO || state == NO_INCOMPLETE ) ? 'show' : 'hide']();
    $('[for="id_user_reason"]')[0].innerHTML = [( state == NO ) ? 'Reason for rejection (user)' : 'Reason for incomplete (user)'];
    $('[for="id_internal_reason"]')[0].innerHTML = [( state == NO ) ? 'Reason for rejection (internal)' : 'Reason for incomplete (internal)'];
}
toggle_fields();
$('[name="state"], [name="expires"]').on('change', toggle_fields);

// For date fields, replace the control with an input group
$('input[type="date"]').each(function() {
    var $input = $(this);
    var $inputGroup = $('<div class="input-group"><span class="input-group-addon"><i class="fa fa-fw fa-calendar"></i></span></div>').insertBefore($input);
    $input.attr('type', 'text').detach().prependTo($inputGroup);
    $input.datepicker({
        'format' : 'yyyy-mm-dd',
        'startDate' : new Date(),
        'autoclose' : true
    });
});

// Replace the textareas with markdown editors
$('textarea').each(function() {
    new SimpleMDE({
        element : this,
        forceSync : true,
        hideIcons : ['heading', 'heading-smaller', 'heading-bigger',
            'heading-1', 'heading-2', 'heading-3', 'image',
            'table', 'quote', 'side-by-side', 'fullscreen'],
        indentWithTabs : false,
        status : false
    });
    // Remove the help text as it is no longer required
    $(this).siblings('.help-block').find('.help-block:not(.error-block)').remove();
})
    </script>
