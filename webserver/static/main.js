$(document).ready(function () {
    docready();
    var tags = $("li").filter(function () {
      return $(this).find("ul").length !== 0;
    });

    tags.each(function () {
      $(this).addClass("parent");
    });

    $("body").find("ul:first-child").attr("id", "treeview");
    $(".parent").prepend("<span>▶</span>");

    $("span").click(function (e) {
      e.stopPropagation();
      e.stopImmediatePropagation();
      $(this).parent( ".parent" ).find(">ul").toggle("slow");
      if ($(this).hasClass("active")) $(this).removeClass("active");
      else $(this).addClass("active");
    });
  });

  if(document.getElementsByTagName("ul").length >= 10){
    var labels = document.querySelectorAll("label");
    //Shorting the file/folder names
    labels.forEach(function (label) {
        if (label.innerText.toString().split(" ").length >= 9) {
            let FirstPart = label.innerText
                .toString()
                .split(" ")
                .slice(0, 5)
                .join(" ");
            let SecondPart = label.innerText
                .toString()
                .split(" ")
                .splice(-5)
                .join(" ");
            label.innerText = `${FirstPart}... ${SecondPart}`;
        }
        if (label.innerText.toString().split(".").length >= 9) {
            let first = label.innerText
                .toString()
                .split(".")
                .slice(0, 5)
                .join(" ");
            let second = label.innerText
                .toString()
                .split(".")
                .splice(-5)
                .join(".");
            label.innerText = `${first}... ${second}`;
        }
    });
}

$('input[type="checkbox"]').change(function(e) {
    var checked = $(this).prop("checked"),
        container = $(this).parent(),
        siblings = container.siblings();
  /*
    $(this).attr('value', function(index, attr){
       return attr == 'yes' ? 'noo' : 'yes';
    });
  */
    container.find('input[type="checkbox"]').prop({
      indeterminate: false,
      checked: checked
    });
    function checkSiblings(el) {
      var parent = el.parent().parent(),
          all = true;
      el.siblings().each(function() {
        let returnValue = all = ($(this).children('input[type="checkbox"]').prop("checked") === checked);
        return returnValue;
      });
  
      if (all && checked) {
        parent.children('input[type="checkbox"]').prop({
          indeterminate: false,
          checked: checked
        });
        checkSiblings(parent);
      } else if (all && !checked) {
        parent.children('input[type="checkbox"]').prop("checked", checked);
        parent.children('input[type="checkbox"]').prop("indeterminate", (parent.find('input[type="checkbox"]:checked').length > 0));
        checkSiblings(parent);
      } else {
        el.parents("li").children('input[type="checkbox"]').prop({
          indeterminate: true,
          checked: false
        });
      }
    }
    checkSiblings(container);
  });


  function docready () {
    $("label[for^='filenode_']").css("cursor", "pointer");
    $("label[for^='filenode_']").click(function () {
        $(this).prev().click();
    });
    checked_size();
    checkingfiles();
    var total_files = $("label[for^='filenode_']").length;
    $("#total_files").text(total_files);
    var total_size = 0;
    var ffilenode = $("label[for^='filenode_']");
    ffilenode.each(function () {
        var size = parseFloat($(this).data("size"));
        total_size += size;
        $(this).append(" - " + humanFileSize(size));
    });
    $("#total_size").text(humanFileSize(total_size));
};
function checked_size() {
    var checked_size = 0;
    var checkedboxes = $("input[name^='filenode_']:checked");
    checkedboxes.each(function () {
        var size = parseFloat($(this).data("size"));
        checked_size += size;
    });
    $("#checked_size").text(humanFileSize(checked_size));
}
function checkingfiles() {
    var checked_files = $("input[name^='filenode_']:checked").length;
    $("#checked_files").text(checked_files);
}
$("input[name^='foldernode_']").change(function () {
    checkingfiles();
    checked_size();
});
$("input[name^='filenode_']").change(function () {
    checkingfiles();
    checked_size();
});
function humanFileSize(size) {
    var i = -1;
    var byteUnits = [' kB', ' MB', ' GB', ' TB', 'PB', 'EB', 'ZB', 'YB'];
    do {
        size = size / 1024;
        i++;
    } while (size > 1024);
    return Math.max(size, 0).toFixed(1) + byteUnits[i];
}
function sticking() {
    var window_top = $(window).scrollTop();
    var div_top = $('.brand').offset().top;
    if (window_top > div_top) {
        $('#sticks').addClass('stick');
    } else {
        $('#sticks').removeClass('stick');
    }
}
$(function () {
    $(window).scroll(sticking);
    sticking();
});