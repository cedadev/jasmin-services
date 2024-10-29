// Constants used in the function below
var YES = 'APPROVED', NO = 'REJECTED', NO_INCOMPLETE = 'INCOMPLETE', CUSTOM_DATE = '7';

// This function makes sure only fields which are needed are shown
var toggle_fields = function() {
    var state = $('[name="state"]').val();
    var expires = $('[name="expires"]').val();
    $('[name="expires"]').closest('div')[state == YES ? 'show' : 'hide']();
    var show_custom = ( state == YES && expires == CUSTOM_DATE );
    $('[name="expires_custom"]').closest('div')[show_custom ? 'show' : 'hide']();
    $('[name$="_reason"]').closest('div')[( state == NO || state == NO_INCOMPLETE ) ? 'show' : 'hide']();
    $('[for="id_user_reason"]')[0].innerHTML = [( state == NO ) ? 'Reason for rejection (user)' : 'Reason for incomplete (user)'];
    $('[name="user_reason"]')[0].placeholder = [( state == NO ) ? 'Reason for rejection (user)' : 'Reason for incomplete (user)'];
    $('[for="id_internal_reason"]')[0].innerHTML = [( state == NO ) ? 'Reason for rejection (internal)' : 'Reason for incomplete (internal)'];
    $('[name="internal_reason"]')[0].placeholder = [( state == NO ) ? 'Reason for rejection (internal)' : 'Reason for incomplete (internal)'];
}
toggle_fields();
$('[name="state"], [name="expires"]').on('change', toggle_fields);

// Replace the textareas with markdown editors
$('textarea').each(function() {
    new EasyMDE({
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
