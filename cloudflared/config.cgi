#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
init_config();
ReadParse();

my $config_file = "/etc/cloudflared/config.yml";

&ui_print_header(undef, "Edit Cloudflared Config", "", undef, 1);

if ($in{'save'}) {
    # Simpan file config
    open(my $fh, '>', $config_file) or die "Cannot open $config_file: $!";
    print $fh $in{'content'};
    close($fh);

    print "<div style='margin:15px; padding:10px; border:1px solid #ccc; background:#f0fff0;'>";
    print "<b style='color:green;'>u{2705} Config saved successfully!</b>";
    print "</div>";
    print "<a class='ui_button' href='config.cgi'>u{21A9} Back to Editor</a> ";
    print "<a class='ui_button' href='index.cgi'>u{21A9} Back to Manager</a>";

} else {
    # Baca isi config
    open(my $fh, '<', $config_file) or die "Cannot open $config_file: $!";
    my @lines = <$fh>;
    close($fh);

    my $content = join('', @lines);

    # Form editor
    print &ui_form_start("config.cgi");
    print &ui_table_start("Cloudflared Config File", "width=80%");
    print &ui_table_row("Configuration (YAML)",
        &ui_textarea("content", $content, 30, 100, undef, undef, "style='font-family:monospace;'"));
    print &ui_table_end();
    print &ui_form_end([ [ "save", "u{1F4BE} Save Config" ] ]);
}

&ui_print_footer("index.cgi", "Back to Manager");

