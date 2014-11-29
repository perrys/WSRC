$(document).on( "mobileinit", function() {
  $(document).on( "pagecontainershow", function( event, ui ) {
    WSRC.onPageContainerShow(event, ui)
  });
});
