$(document).on( "mobileinit", function() {
  $(document).on( "pagecontainershow", function( event, ui ) {
    if (window.WSRC === undefined)
      window.WSRC_deferedPageContainerShow = [event, ui]
    else
      WSRC.onPageContainerShow(event, ui)
  });
});
